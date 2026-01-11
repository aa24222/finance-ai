import os
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, request
from flask_cors import CORS
from analysis_engine import FinancialAnalyzer
from auth_middleware import require_auth, get_user_data_path, get_user_csv_path
from werkzeug.utils import secure_filename
import traceback

app = Flask(__name__)

# CORS configuration
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://localhost:5173", "https://yourdomain.com"],
        "methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# ========== Configuration ==========
DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
DEMO_DATA_PATH = os.path.join(DATA_FOLDER, 'financial_transactions.csv')
USER_DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'user_data')
ALLOWED_EXTENSIONS = {'csv'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE
os.makedirs(USER_DATA_FOLDER, exist_ok=True)

# Analyzer cache keyed by user_id
analyzers = {}


def allowed_file(filename):
    return bool(filename) and '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _validate_csv_schema(file_path):
    import pandas as pd
    df = pd.read_csv(file_path)
    df.columns = [c.strip().lower() for c in df.columns]

    required = {'date', 'merchant', 'category', 'amount', 'type'}
    missing = required - set(df.columns)
    if missing:
        return False, {
            'error': f'Missing required columns: {", ".join(sorted(missing))}',
            'required_columns': sorted(list(required)),
            'your_columns': list(df.columns),
        }
    if df.empty:
        return False, {'error': 'CSV file is empty'}
    return True, {'row_count': int(len(df)), 'columns': list(df.columns)}


def get_analyzer_for_user(user_id):
    """Get or create analyzer for user. Falls back to demo data."""
    if not user_id:
        if 'demo' not in analyzers:
            analyzers['demo'] = FinancialAnalyzer(DEMO_DATA_PATH)
        return analyzers['demo'], 'demo', os.path.basename(DEMO_DATA_PATH)

    user_csv = get_user_csv_path(user_id)
    if user_csv:
        if user_id not in analyzers:
            analyzers[user_id] = FinancialAnalyzer(user_csv)
        return analyzers[user_id], 'uploaded', 'transactions.csv'

    if 'demo' not in analyzers:
        analyzers['demo'] = FinancialAnalyzer(DEMO_DATA_PATH)
    return analyzers['demo'], 'demo', os.path.basename(DEMO_DATA_PATH)


def reload_user_analyzer(user_id, file_path):
    """Reload analyzer for user with new data."""
    try:
        analyzers[user_id] = FinancialAnalyzer(file_path)
        return True
    except Exception as e:
        print(f"Error loading analyzer: {e}")
        return False


def clear_user_analyzer(user_id):
    """Clear cached analyzer for user."""
    if user_id in analyzers:
        del analyzers[user_id]


def get_mode_from_request():
    mode = request.args.get('mode', 'ytd')
    mode = (mode or 'ytd').strip().lower()

    if mode in ('year_to_date', 'year-to-date', 'ytd'):
        mode = 'ytd'
    elif mode in ('this_month', 'this-month'):
        mode = 'this_month'
    elif mode in ('last_month', 'last-month'):
        mode = 'last_month'

    allowed = {'this_month', 'last_month', 'ytd'}
    if mode not in allowed:
        return None, jsonify({
            'success': False,
            'error': 'Invalid mode. Use one of: this_month, last_month, ytd',
        }), 400
    return mode, None, None


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


# ========== CSV Upload Endpoints ==========
@app.route('/api/data/upload', methods=['POST'])
@require_auth
def upload_csv():
    """Upload CSV for authenticated user."""
    try:
        user = request.current_user
        user_id = user['id']

        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Invalid file type. Only CSV allowed.'}), 400

        user_path = get_user_data_path(user_id)
        file_path = os.path.join(user_path, 'transactions.csv')
        file.save(file_path)

        ok, info = _validate_csv_schema(file_path)
        if not ok:
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({'success': False, **info}), 400

        if reload_user_analyzer(user_id, file_path):
            return jsonify({
                'success': True,
                'message': 'Successfully loaded your data',
                'data_source': 'uploaded',
                'file_name': secure_filename(file.filename),
                'row_count': info.get('row_count', 0),
            })

        return jsonify({'success': False, 'error': 'Failed to process CSV'}), 500

    except Exception as e:
        print(f"Error in /api/data/upload: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/data/reset', methods=['POST'])
@require_auth
def reset_to_demo():
    """Reset user to demo data."""
    try:
        user = request.current_user
        user_id = user['id']

        user_csv = get_user_csv_path(user_id)
        if user_csv and os.path.exists(user_csv):
            os.remove(user_csv)

        clear_user_analyzer(user_id)

        return jsonify({
            'success': True,
            'message': 'Reset to demo data',
            'data_source': 'demo',
            'file_name': os.path.basename(DEMO_DATA_PATH),
        })

    except Exception as e:
        print(f"Error in /api/data/reset: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/data/status', methods=['GET'])
@require_auth
def data_status():
    """Get data status for authenticated user."""
    try:
        user = request.current_user
        analyzer, data_source, file_name = get_analyzer_for_user(user['id'])

        mode, err_resp, err_code = get_mode_from_request()
        if err_resp:
            return err_resp, err_code

        stats = analyzer.get_summary_stats(mode=mode)
        row_count = int(analyzer.df.shape[0]) if hasattr(analyzer, 'df') else 0

        return jsonify({
            'success': True,
            'data_loaded': True,
            'data_source': data_source,
            'file_name': file_name,
            'row_count': row_count,
            'date_range': stats.get('date_range'),
            'mode': mode,
        })

    except Exception as e:
        print(f"Error in /api/data/status: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/data/template', methods=['GET'])
def get_csv_template():
    return jsonify({
        'success': True,
        'required_columns': ['date', 'merchant', 'category', 'amount', 'type'],
        'optional_columns': ['transaction_id', 'description', 'transaction_tag'],
        'column_descriptions': {
            'transaction_id': 'Unique transaction id (optional)',
            'date': 'Transaction date (YYYY-MM-DD or M/D/YYYY)',
            'description': 'Free-text description (optional)',
            'merchant': 'Name of the merchant/store',
            'category': 'Spending category',
            'amount': 'Transaction amount (negative for expenses)',
            'type': 'debit or credit',
            'transaction_tag': 'normal | subscription | bill (optional)',
        },
        'example_row': {
            'date': '2024-01-15',
            'merchant': 'Netflix',
            'category': 'Entertainment',
            'amount': -15.99,
            'type': 'debit',
            'transaction_tag': 'subscription',
        }
    })


# ========== Security Info ==========
@app.route('/api/security', methods=['GET'])
def security_info():
    return jsonify({
        'data_storage': 'Per-user encrypted storage',
        'authentication': 'JWT-based via Supabase',
        'encryption': 'HTTPS in production',
        'data_retention': 'User-controlled',
        'third_party': 'No data shared',
    })


# ========== Health Check ==========
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'API running'})


# ========== Dashboard Summary ==========
@app.route('/api/summary', methods=['GET'])
@require_auth
def get_summary():
    try:
        user = request.current_user
        analyzer, data_source, _ = get_analyzer_for_user(user['id'])

        mode, err_resp, err_code = get_mode_from_request()
        if err_resp:
            return err_resp, err_code

        stats = analyzer.get_summary_stats(mode=mode)
        categories = analyzer.get_spending_by_category(mode=mode)

        return jsonify({
            'success': True,
            'stats': stats,
            'categories': categories,
            'data_source': data_source,
            'mode': mode,
        })

    except Exception as e:
        print(f"Error in /api/summary: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== Spending Habits ==========
@app.route('/api/insights/spending', methods=['GET'])
@require_auth
def get_spending_insights():
    try:
        user = request.current_user
        analyzer, _, _ = get_analyzer_for_user(user['id'])

        mode, err_resp, err_code = get_mode_from_request()
        if err_resp:
            return err_resp, err_code

        result = analyzer.detect_spending_habits(mode=mode)
        if result is None:
            return jsonify({'success': True, 'found': False, 'mode': mode})

        return jsonify({'success': True, 'found': True, 'data': result, 'mode': mode})

    except Exception as e:
        print(f"Error in /api/insights/spending: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== Anomaly Detection ==========
@app.route('/api/insights/anomalies', methods=['GET'])
@require_auth
def get_anomalies():
    try:
        user = request.current_user
        analyzer, _, _ = get_analyzer_for_user(user['id'])

        mode, err_resp, err_code = get_mode_from_request()
        if err_resp:
            return err_resp, err_code

        contamination = float(request.args.get('contamination', 0.05))
        if not (0.0 < contamination <= 0.5):
            return jsonify({'success': False, 'error': 'Contamination must be 0-0.5'}), 400

        result = analyzer.detect_anomalies(contamination=contamination, mode=mode)
        if result is None:
            return jsonify({'success': True, 'found': False, 'mode': mode})

        return jsonify({'success': True, 'found': result.get('found', False), 'data': result, 'mode': mode})

    except Exception as e:
        print(f"Error in /api/insights/anomalies: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== Subscriptions ==========
@app.route('/api/insights/subscriptions', methods=['GET'])
@require_auth
def get_subscriptions():
    try:
        user = request.current_user
        analyzer, _, _ = get_analyzer_for_user(user['id'])

        mode, err_resp, err_code = get_mode_from_request()
        if err_resp:
            return err_resp, err_code

        result = analyzer.detect_subscriptions(mode=mode)
        return jsonify({'success': True, 'data': result, 'mode': mode})

    except Exception as e:
        print(f"Error in /api/insights/subscriptions: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== Goal Forecasting ==========
@app.route('/api/insights/goal', methods=['POST'])
@require_auth
def forecast_goal():
    try:
        user = request.current_user
        analyzer, _, _ = get_analyzer_for_user(user['id'])

        payload = request.get_json(silent=True) or {}
        goal_amount = float(payload.get('goal_amount', 3000))
        goal_months = int(payload.get('goal_months', 10))

        mode = payload.get('mode', request.args.get('mode', 'ytd'))
        mode = (mode or 'ytd').strip().lower()
        if mode in ('year_to_date', 'year-to-date', 'ytd'):
            mode = 'ytd'
        elif mode in ('this_month', 'this-month'):
            mode = 'this_month'
        elif mode in ('last_month', 'last-month'):
            mode = 'last_month'
        if mode not in {'this_month', 'last_month', 'ytd'}:
            return jsonify({'success': False, 'error': 'Invalid mode'}), 400

        if goal_amount <= 0 or goal_months <= 0:
            return jsonify({'success': False, 'error': 'Values must be positive'}), 400
        if goal_amount > 1_000_000:
            return jsonify({'success': False, 'error': 'Goal exceeds $1M limit'}), 400
        if goal_months > 120:
            return jsonify({'success': False, 'error': 'Timeframe exceeds 10 years'}), 400

        result = analyzer.forecast_goal(goal_amount, goal_months, mode=mode)
        return jsonify({'success': True, 'data': result, 'mode': mode})

    except Exception as e:
        print(f"Error in /api/insights/goal: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== Timeline ==========
@app.route('/api/timeline', methods=['GET'])
@require_auth
def get_timeline():
    try:
        user = request.current_user
        analyzer, _, _ = get_analyzer_for_user(user['id'])

        mode, err_resp, err_code = get_mode_from_request()
        if err_resp:
            return err_resp, err_code

        timeline = analyzer.get_timeline_data(mode=mode)
        return jsonify({'success': True, 'data': timeline, 'mode': mode})

    except Exception as e:
        print(f"Error in /api/timeline: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== Category Trends ==========
@app.route('/api/trends', methods=['GET'])
@require_auth
def get_trends():
    try:
        user = request.current_user
        analyzer, _, _ = get_analyzer_for_user(user['id'])

        mode, err_resp, err_code = get_mode_from_request()
        if err_resp:
            return err_resp, err_code

        trends = analyzer.get_category_trends(mode=mode)
        return jsonify({'success': True, 'data': trends, 'mode': mode})

    except Exception as e:
        print(f"Error in /api/trends: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== Error Handlers ==========
@app.errorhandler(404)
def not_found(_):
    return jsonify({'success': False, 'error': 'Endpoint not found'}), 404


@app.errorhandler(500)
def internal_error(_):
    return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ========== Main ==========
if __name__ == '__main__':
    print("\n" + "=" * 60)
    print(" Smart Financial Coach API")
    print("=" * 60)
    print(f"Demo data: {DEMO_DATA_PATH}")
    print(f"User data: {USER_DATA_FOLDER}")
    print(f"Running on: http://localhost:5000")
    print("Auth: Supabase JWT")
    print("=" * 60 + "\n")

    app.run(debug=True, port=5000, host='0.0.0.0')