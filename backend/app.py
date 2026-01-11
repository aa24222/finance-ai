from flask import Flask, jsonify, request
from flask_cors import CORS
from analysis_engine import FinancialAnalyzer
from werkzeug.utils import secure_filename
import os
import traceback

app = Flask(__name__)

# CORS configuration
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000", "http://localhost:5173", "https://yourdomain.com"],
        "methods": ["GET", "POST", "DELETE"],
        "allow_headers": ["Content-Type"]
    }
})

# ========== Configuration ==========
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data')
DEMO_DATA_PATH = os.path.join(DATA_FOLDER, 'financial_transactions.csv')
ALLOWED_EXTENSIONS = {'csv'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global state
analyzer = None
current_data_source = 'demo'
current_file_name = os.path.basename(DEMO_DATA_PATH)


def allowed_file(filename):
    # Extension allowlist
    return bool(filename) and '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _validate_csv_schema(file_path):
    # Minimal schema validation before loading into analyzer
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


def load_analyzer(file_path, source_name='demo', file_name=None):
    global analyzer, current_data_source, current_file_name
    try:
        analyzer = FinancialAnalyzer(file_path)
        current_data_source = source_name
        current_file_name = file_name or os.path.basename(file_path)
        print(f"✓ Loaded data from: {file_path}")
        return True
    except Exception as e:
        print(f"✗ Error loading data: {e}")
        return False


def get_mode_from_request():
    mode = request.args.get('mode', 'ytd')
    mode = (mode or 'ytd').strip().lower()

    # Normalize common aliases
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
            'allowed_modes': ['this_month', 'last_month', 'ytd'],
        }), 400

    return mode, None, None


# Initialize with demo data on startup
load_analyzer(DEMO_DATA_PATH, 'demo', os.path.basename(DEMO_DATA_PATH))


@app.after_request
def add_security_headers(response):
    # Baseline headers (OK for local dev; adjust HSTS for production HTTPS)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


def require_analyzer():
    # Centralized guard for endpoints that need data loaded
    if analyzer is None:
        return jsonify({'success': False, 'error': 'Data not loaded'}), 500
    return None


# ========== CSV Upload Endpoints ==========
@app.route('/api/data/upload', methods=['POST'])
def upload_csv():
    """
    Upload a CSV file to use as the data source
    Required columns: date, merchant, category, amount, type
    Optional columns: transaction_id, description, transaction_tag
    """
    try:
        # Validate request payload
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided. Please include a CSV file.'}), 400

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Invalid file type. Only CSV files are allowed.'}), 400

        # Save to uploads folder
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Validate schema before loading analyzer
        ok, info = _validate_csv_schema(file_path)
        if not ok:
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({'success': False, **info}), 400

        # Load analyzer
        if load_analyzer(file_path, 'uploaded', filename):
            return jsonify({
                'success': True,
                'message': f'Successfully loaded {filename}',
                'data_source': 'uploaded',
                'file_name': filename,
                'row_count': info.get('row_count', 0),
                'columns': info.get('columns', []),
            })

        if os.path.exists(file_path):
            os.remove(file_path)
        return jsonify({'success': False, 'error': 'Failed to process the CSV file'}), 500

    except Exception as e:
        print(f"Error in /api/data/upload: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/data/reset', methods=['POST'])
def reset_to_demo():
    try:
        if load_analyzer(DEMO_DATA_PATH, 'demo', os.path.basename(DEMO_DATA_PATH)):
            return jsonify({
                'success': True,
                'message': 'Reset to demo data',
                'data_source': 'demo',
                'file_name': os.path.basename(DEMO_DATA_PATH),
            })
        return jsonify({'success': False, 'error': 'Failed to load demo data'}), 500
    except Exception as e:
        print(f"Error in /api/data/reset: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/data/status', methods=['GET'])
def data_status():
    try:
        if analyzer is None:
            return jsonify({
                'success': True,
                'data_loaded': False,
                'data_source': None,
                'file_name': None,
                'row_count': 0,
                'date_range': None,
            })

        mode, err_resp, err_code = get_mode_from_request()
        if err_resp:
            return err_resp, err_code

        stats = analyzer.get_summary_stats(mode=mode)
        row_count = int(getattr(analyzer, 'df', []).shape[0]) if hasattr(analyzer, 'df') else 0

        return jsonify({
            'success': True,
            'data_loaded': True,
            'data_source': current_data_source,
            'file_name': current_file_name,
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
            'category': 'Spending category (e.g., Groceries, Dining Out, etc.)',
            'amount': 'Transaction amount (negative for expenses, positive for income)',
            'type': 'Transaction type: "debit" for expenses, "credit" for income',
            'transaction_tag': 'One of: normal | subscription | bill (optional)',
        },
        'example_row': {
            'transaction_id': 'TXN000001',
            'date': '2024-01-15',
            'description': 'Netflix Subscription',
            'merchant': 'Netflix',
            'category': 'Entertainment',
            'amount': -15.99,
            'type': 'debit',
            'transaction_tag': 'subscription',
        }
    })


# ========== Security Info Endpoint ==========
@app.route('/api/security', methods=['GET'])
def security_info():
    return jsonify({
        'data_storage': 'Local processing only - no cloud storage',
        'encryption': 'Data encrypted in transit (HTTPS in production)',
        'data_retention': 'No transaction data retained after session',
        'third_party': 'No data shared with third parties',
        'compliance': 'Designed for GDPR compliance',
        'open_source': 'Code available for security audit',
    })


# ========== Health Check ==========
@app.route('/api/health', methods=['GET'])
def health_check():
    if analyzer is None:
        return jsonify({'status': 'error', 'message': 'Data not loaded'}), 500
    return jsonify({
        'status': 'ok',
        'message': 'Smart Financial Coach API is running',
        'data_source': current_data_source,
    })


# ========== Dashboard Summary ==========
@app.route('/api/summary', methods=['GET'])
def get_summary():
    guard = require_analyzer()
    if guard:
        return guard

    try:
        mode, err_resp, err_code = get_mode_from_request()
        if err_resp:
            return err_resp, err_code

        stats = analyzer.get_summary_stats(mode=mode)
        categories = analyzer.get_spending_by_category(mode=mode)
        return jsonify({
            'success': True,
            'stats': stats,
            'categories': categories,
            'data_source': current_data_source,
            'mode': mode,
        })
    except Exception as e:
        print(f"Error in /api/summary: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== Spending Habits Insights ==========
@app.route('/api/insights/spending', methods=['GET'])
def get_spending_insights():
    guard = require_analyzer()
    if guard:
        return guard

    try:
        mode, err_resp, err_code = get_mode_from_request()
        if err_resp:
            return err_resp, err_code

        result = analyzer.detect_spending_habits(mode=mode)
        if result is None:
            return jsonify({'success': True, 'found': False, 'message': 'No frequent spending habits detected', 'mode': mode})
        return jsonify({'success': True, 'found': True, 'data': result, 'mode': mode})
    except Exception as e:
        print(f"Error in /api/insights/spending: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== AI Anomaly Detection ==========
@app.route('/api/insights/anomalies', methods=['GET'])
def get_anomalies():
    guard = require_analyzer()
    if guard:
        return guard

    try:
        mode, err_resp, err_code = get_mode_from_request()
        if err_resp:
            return err_resp, err_code

        contamination = float(request.args.get('contamination', 0.05))
        if not (0.0 < contamination <= 0.5):
            return jsonify({'success': False, 'error': 'Contamination rate must be between 0 and 0.5'}), 400

        result = analyzer.detect_anomalies(contamination=contamination, mode=mode)
        if result is None:
            return jsonify({'success': True, 'found': False, 'message': 'Not enough data for anomaly detection', 'mode': mode})

        return jsonify({'success': True, 'found': result.get('found', False), 'data': result, 'mode': mode})
    except Exception as e:
        print(f"Error in /api/insights/anomalies: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== Subscription Detector ==========
@app.route('/api/insights/subscriptions', methods=['GET'])
def get_subscriptions():
    guard = require_analyzer()
    if guard:
        return guard

    try:
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
def forecast_goal():
    guard = require_analyzer()
    if guard:
        return guard

    try:
        payload = request.get_json(silent=True) or {}

        # Parse inputs
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
            return jsonify({
                'success': False,
                'error': 'Invalid mode. Use one of: this_month, last_month, ytd',
                'allowed_modes': ['this_month', 'last_month', 'ytd'],
            }), 400

        # Basic validation
        if goal_amount <= 0 or goal_months <= 0:
            return jsonify({'success': False, 'error': 'Goal amount and months must be positive'}), 400
        if goal_amount > 1_000_000:
            return jsonify({'success': False, 'error': 'Goal amount exceeds maximum allowed ($1,000,000)'}), 400
        if goal_months > 120:
            return jsonify({'success': False, 'error': 'Goal timeframe exceeds maximum (10 years)'}), 400

        # Run forecast
        result = analyzer.forecast_goal(goal_amount, goal_months, mode=mode)
        return jsonify({'success': True, 'data': result, 'mode': mode})

    except Exception as e:
        print(f"Error in /api/insights/goal: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ========== Timeline Data ==========
@app.route('/api/timeline', methods=['GET'])
def get_timeline():
    guard = require_analyzer()
    if guard:
        return guard

    try:
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
def get_trends():
    guard = require_analyzer()
    if guard:
        return guard

    try:
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
    print(" Smart Financial Coach API Starting...")
    print("=" * 60)
    print(f"📁 Demo data: {DEMO_DATA_PATH}")
    print(f"📂 Upload folder: {UPLOAD_FOLDER}")
    print(f"🌐 API running on: http://localhost:5000")

    print("\n📋 API Endpoints:")
    print("   GET  /api/health                 - Health check")
    print("   GET  /api/summary                - Financial summary (mode=this_month|last_month|ytd)")
    print("   GET  /api/insights/spending      - Spending habits analysis (mode=this_month|last_month|ytd)")
    print("   GET  /api/insights/anomalies     - AI anomaly detection (mode=this_month|last_month|ytd)")
    print("   GET  /api/insights/subscriptions - Subscription detector (mode=this_month|last_month|ytd)")
    print("   POST /api/insights/goal          - Goal forecasting (mode in JSON body or ?mode=...)")
    print("   GET  /api/security               - Security & privacy info")
    print("   GET  /api/timeline               - Daily spending timeline (mode=this_month|last_month|ytd)")
    print("   GET  /api/trends                 - Category trends (mode=this_month|last_month|ytd)")

    print("\n📤 Data Upload Endpoints:")
    print("   POST /api/data/upload            - Upload CSV file")
    print("   POST /api/data/reset             - Reset to demo data")
    print("   GET  /api/data/status            - Current data source info (mode=this_month|last_month|ytd)")
    print("   GET  /api/data/template          - Get CSV format template")
    print("=" * 60 + "\n")

    app.run(debug=True, port=5000, host='0.0.0.0')
