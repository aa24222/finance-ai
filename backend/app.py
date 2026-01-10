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

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Global state
analyzer = None
current_data_source = 'demo'
current_file_name = 'financial_transactions.csv'

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def load_analyzer(file_path, source_name='demo', file_name=None):
    """Load or reload the analyzer with new data"""
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

# Initialize with demo data on startup
load_analyzer(DEMO_DATA_PATH, 'demo', 'financial_transactions.csv')

# ========== Security Headers ==========
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# ========== CSV Upload Endpoints ==========
@app.route('/api/data/upload', methods=['POST'])
def upload_csv():
    """
    Upload a CSV file to use as the data source
    Expected CSV columns: date, merchant, category, amount, type
    """
    global analyzer
    
    try:
        # Check if file was included in request
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided. Please include a CSV file.'
            }), 400
        
        file = request.files['file']
        
        # Check if a file was selected
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Validate file extension
        if not allowed_file(file.filename):
            return jsonify({
                'success': False,
                'error': 'Invalid file type. Only CSV files are allowed.'
            }), 400
        
        # Secure the filename and save
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # Validate CSV structure before loading
        import pandas as pd
        try:
            df = pd.read_csv(file_path)
            required_columns = {'date', 'merchant', 'category', 'amount', 'type'}
            missing_columns = required_columns - set(df.columns.str.lower())
            
            if missing_columns:
                os.remove(file_path)  # Clean up invalid file
                return jsonify({
                    'success': False,
                    'error': f'Missing required columns: {", ".join(missing_columns)}',
                    'required_columns': list(required_columns),
                    'your_columns': list(df.columns)
                }), 400
            
            # Check if file has data
            if len(df) == 0:
                os.remove(file_path)
                return jsonify({
                    'success': False,
                    'error': 'CSV file is empty'
                }), 400
                
        except Exception as e:
            os.remove(file_path)
            return jsonify({
                'success': False,
                'error': f'Invalid CSV format: {str(e)}'
            }), 400
        
        # Load the new data into analyzer
        if load_analyzer(file_path, 'uploaded', filename):
            return jsonify({
                'success': True,
                'message': f'Successfully loaded {filename}',
                'data_source': 'uploaded',
                'file_name': filename,
                'row_count': len(df)
            })
        else:
            os.remove(file_path)
            return jsonify({
                'success': False,
                'error': 'Failed to process the CSV file'
            }), 500
            
    except Exception as e:
        print(f"Error in /api/data/upload: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/data/reset', methods=['POST'])
def reset_to_demo():
    """Reset to using demo data"""
    try:
        if load_analyzer(DEMO_DATA_PATH, 'demo', 'financial_transactions.csv'):
            return jsonify({
                'success': True,
                'message': 'Reset to demo data',
                'data_source': 'demo',
                'file_name': 'financial_transactions.csv'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to load demo data'
            }), 500
    except Exception as e:
        print(f"Error in /api/data/reset: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/data/status', methods=['GET'])
def data_status():
    """Get current data source status"""
    try:
        if analyzer is None:
            return jsonify({
                'success': True,
                'data_loaded': False,
                'data_source': None,
                'file_name': None
            })
        
        stats = analyzer.get_summary_stats()
        
        return jsonify({
            'success': True,
            'data_loaded': True,
            'data_source': current_data_source,
            'file_name': current_file_name,
            'row_count': stats['date_range']['days'],
            'date_range': stats['date_range']
        })
    except Exception as e:
        print(f"Error in /api/data/status: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/data/template', methods=['GET'])
def get_csv_template():
    """Return the expected CSV format"""
    return jsonify({
        'success': True,
        'required_columns': ['date', 'merchant', 'category', 'amount', 'type'],
        'column_descriptions': {
            'date': 'Transaction date (YYYY-MM-DD format)',
            'merchant': 'Name of the merchant/store',
            'category': 'Spending category (e.g., Food & Dining, Shopping, etc.)',
            'amount': 'Transaction amount (negative for expenses, positive for income)',
            'type': 'Transaction type: "debit" for expenses, "credit" for income'
        },
        'example_row': {
            'date': '2024-01-15',
            'merchant': 'Starbucks',
            'category': 'Food & Dining',
            'amount': -5.75,
            'type': 'debit'
        }
    })

# ========== Security Info Endpoint ==========
@app.route('/api/security', methods=['GET'])
def security_info():
    """Return security and privacy information"""
    return jsonify({
        'data_storage': 'Local processing only - no cloud storage',
        'encryption': 'Data encrypted in transit (HTTPS in production)',
        'data_retention': 'No transaction data retained after session',
        'third_party': 'No data shared with third parties',
        'compliance': 'Designed for GDPR compliance',
        'open_source': 'Code available for security audit'
    })

# ========== Health Check ==========
@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    if analyzer is None:
        return jsonify({
            'status': 'error',
            'message': 'Data not loaded'
        }), 500
    
    return jsonify({
        'status': 'ok',
        'message': 'Smart Financial Coach API is running',
        'data_source': current_data_source
    })

# ========== Dashboard Summary ==========
@app.route('/api/summary', methods=['GET'])
def get_summary():
    """Get overall financial summary and spending by category"""
    try:
        if analyzer is None:
            return jsonify({'success': False, 'error': 'Data not loaded'}), 500
        
        stats = analyzer.get_summary_stats()
        categories = analyzer.get_spending_by_category()
        
        return jsonify({
            'success': True,
            'stats': stats,
            'categories': categories,
            'data_source': current_data_source
        })
    except Exception as e:
        print(f"Error in /api/summary: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== Spending Habits Insights (Feature 1) ==========
@app.route('/api/insights/spending', methods=['GET'])
def get_spending_insights():
    """
    Analyze spending habits using data-driven pattern detection
    Returns: Spending habit analysis with savings potential
    """
    try:
        if analyzer is None:
            return jsonify({'success': False, 'error': 'Data not loaded'}), 500
        
        result = analyzer.detect_spending_habits()
        
        if result is None:
            return jsonify({
                'success': True,
                'found': False,
                'message': 'No frequent spending habits detected'
            })
        
        return jsonify({
            'success': True,
            'found': True,
            'data': result
        })
    except Exception as e:
        print(f"Error in /api/insights/spending: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== AI Anomaly Detection ==========
@app.route('/api/insights/anomalies', methods=['GET'])
def get_anomalies():
    """
    AI-powered anomaly detection using Isolation Forest
    Returns: Unusual transactions that may indicate fraud, errors, or unexpected charges
    """
    try:
        if analyzer is None:
            return jsonify({'success': False, 'error': 'Data not loaded'}), 500
        
        # Optional: Allow custom contamination rate via query parameter
        contamination = float(request.args.get('contamination', 0.05))
        
        # Validate contamination rate (must be between 0 and 0.5)
        if contamination <= 0 or contamination > 0.5:
            return jsonify({
                'success': False,
                'error': 'Contamination rate must be between 0 and 0.5'
            }), 400
        
        result = analyzer.detect_anomalies(contamination=contamination)
        
        if result is None:
            return jsonify({
                'success': True,
                'found': False,
                'message': 'Not enough data for anomaly detection'
            })
        
        return jsonify({
            'success': True,
            'found': result.get('found', False),
            'data': result
        })
    except Exception as e:
        print(f"Error in /api/insights/anomalies: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== Subscription Detector (Feature 2) ==========
@app.route('/api/insights/subscriptions', methods=['GET'])
def get_subscriptions():
    """
    Detect recurring subscriptions
    Returns: List of subscriptions with unused detection
    """
    try:
        if analyzer is None:
            return jsonify({'success': False, 'error': 'Data not loaded'}), 500
        
        result = analyzer.detect_subscriptions()
        
        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        print(f"Error in /api/insights/subscriptions: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== Goal Forecasting (Feature 3) ==========
@app.route('/api/insights/goal', methods=['POST'])
def forecast_goal():
    """
    Forecast savings goal achievement
    Request body: { "goal_amount": 3000, "goal_months": 10 }
    Returns: Goal forecast with personalized recommendations
    """
    try:
        if analyzer is None:
            return jsonify({'success': False, 'error': 'Data not loaded'}), 500
        
        data = request.json
        goal_amount = float(data.get('goal_amount', 3000))
        goal_months = int(data.get('goal_months', 10))
        
        # Input validation
        if goal_amount > 1000000:
            return jsonify({
                'success': False,
                'error': 'Goal amount exceeds maximum allowed ($1,000,000)'
            }), 400
        
        if goal_months > 120:
            return jsonify({
                'success': False,
                'error': 'Goal timeframe exceeds maximum (10 years)'
            }), 400
        
        result = analyzer.forecast_goal(goal_amount, goal_months)
        
        return jsonify({
            'success': True,
            'data': result
        })
    
    except Exception as e:
        print(f"Error in /api/insights/goal: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== Timeline Data for Charts ==========
@app.route('/api/timeline', methods=['GET'])
def get_timeline():
    """
    Get daily spending timeline for visualization
    Returns: Array of {date, amount} objects
    """
    try:
        if analyzer is None:
            return jsonify({'success': False, 'error': 'Data not loaded'}), 500
        
        timeline = analyzer.get_timeline_data()
        
        return jsonify({
            'success': True,
            'data': timeline
        })
    except Exception as e:
        print(f"Error in /api/timeline: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== Category Trends ==========
@app.route('/api/trends', methods=['GET'])
def get_trends():
    """
    Get spending trends by category over time
    Returns: Monthly spending by category
    """
    try:
        if analyzer is None:
            return jsonify({'success': False, 'error': 'Data not loaded'}), 500
        
        trends = analyzer.get_category_trends()
        
        return jsonify({
            'success': True,
            'data': trends
        })
    except Exception as e:
        print(f"Error in /api/trends: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== Error Handlers ==========
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

# ========== Main ==========
if __name__ == '__main__':
    print("\n" + "="*60)
    print(" Smart Financial Coach API Starting...")
    print("="*60)
    print(f"📁 Demo data: {DEMO_DATA_PATH}")
    print(f"📂 Upload folder: {UPLOAD_FOLDER}")
    print(f"🌐 API running on: http://localhost:5000")
    print(f"\n📋 API Endpoints:")
    print(f"   GET  /api/health                 - Health check")
    print(f"   GET  /api/summary                - Financial summary")
    print(f"   GET  /api/insights/spending      - Spending habits analysis")
    print(f"   GET  /api/insights/anomalies     - AI anomaly detection")
    print(f"   GET  /api/insights/subscriptions - Subscription detector")
    print(f"   POST /api/insights/goal          - Goal forecasting")
    print(f"   GET  /api/security               - Security & privacy info")
    print(f"   GET  /api/timeline               - Daily spending timeline")
    print(f"   GET  /api/trends                 - Category trends")
    print(f"\n📤 Data Upload Endpoints:")
    print(f"   POST /api/data/upload            - Upload CSV file")
    print(f"   POST /api/data/reset             - Reset to demo data")
    print(f"   GET  /api/data/status            - Current data source info")
    print(f"   GET  /api/data/template          - Get CSV format template")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000, host='0.0.0.0')