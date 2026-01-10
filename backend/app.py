from flask import Flask, jsonify, request
from flask_cors import CORS
from analysis_engine import FinancialAnalyzer
import os
import traceback

app = Flask(__name__)
CORS(app)  # Enable CORS for React frontend

# Initialize analyzer with data
DATA_PATH = os.path.join(os.path.dirname(__file__), 'data', 'financial_transactions.csv')

try:
    analyzer = FinancialAnalyzer(DATA_PATH)
    print(f"Loaded financial data from {DATA_PATH}")
except Exception as e:
    print(f"Error loading data: {e}")
    analyzer = None

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
        'message': 'Smart Financial Coach API is running'
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
            'categories': categories
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
        
        # Validate inputs
        if goal_amount <= 0 or goal_months <= 0:
            return jsonify({
                'success': False,
                'error': 'Goal amount and months must be positive'
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
    print("\n" + "="*50)
    print("Smart Financial Coach API Starting...")
    print("="*50)
    print(f"Data file: {DATA_PATH}")
    print(f"API running on: http://localhost:5000")
    print(f"API Documentation:")
    print(f"   GET  /api/health              - Health check")
    print(f"   GET  /api/summary             - Financial summary")
    print(f"   GET  /api/insights/spending   - Spending habits analysis")
    print(f"   GET  /api/insights/anomalies  - AI anomaly detection")
    print(f"   GET  /api/insights/subscriptions - Subscription detector")
    print(f"   POST /api/insights/goal       - Goal forecasting")
    print(f"   GET  /api/timeline            - Daily spending timeline")
    print(f"   GET  /api/trends              - Category trends")
    print("="*50 + "\n")
    
    app.run(debug=True, port=5000, host='0.0.0.0')