"""
Authentication middleware for Supabase JWT verification.
Verifies tokens and extracts user information.
"""
import os
import jwt
from functools import wraps
from flask import request, jsonify

# Supabase JWT settings
SUPABASE_JWT_SECRET = os.environ.get('SUPABASE_JWT_SECRET', '')
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')

# For development: if no secret set, allow requests without auth
DEV_MODE = not SUPABASE_JWT_SECRET


def get_user_from_token():
    """
    Extract and verify user from the Authorization header.
    Returns user dict or None if invalid/missing.
    """
    auth_header = request.headers.get('Authorization', '')

    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]  # Remove 'Bearer ' prefix

    if DEV_MODE:
        # In dev mode without JWT secret, decode without verification
        # This is only for local development!
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            return {
                'id': payload.get('sub'),
                'email': payload.get('email'),
                'role': payload.get('role', 'authenticated'),
            }
        except Exception:
            return None

    try:
        # Verify with Supabase JWT secret
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=['HS256'],
            audience='authenticated',
        )
        return {
            'id': payload.get('sub'),
            'email': payload.get('email'),
            'role': payload.get('role', 'authenticated'),
        }
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def require_auth(f):
    """
    Decorator that requires a valid JWT token.
    Adds 'current_user' to the request context.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_user_from_token()

        if user is None:
            return jsonify({
                'success': False,
                'error': 'Authentication required',
                'code': 'UNAUTHORIZED'
            }), 401

        # Add user to request context
        request.current_user = user
        return f(*args, **kwargs)

    return decorated


def optional_auth(f):
    """
    Decorator that optionally extracts user from JWT.
    Sets 'current_user' to user dict or None.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_user_from_token()
        request.current_user = user
        return f(*args, **kwargs)

    return decorated


def get_user_data_path(user_id):
    """
    Get the path to a user's data directory.
    Creates the directory if it doesn't exist.
    """
    base_path = os.path.join(os.path.dirname(__file__), 'user_data')
    user_path = os.path.join(base_path, user_id)
    os.makedirs(user_path, exist_ok=True)
    return user_path


def get_user_csv_path(user_id):
    """
    Get the path to a user's uploaded CSV file.
    Returns None if no file exists.
    """
    user_path = get_user_data_path(user_id)
    csv_path = os.path.join(user_path, 'transactions.csv')

    if os.path.exists(csv_path):
        return csv_path
    return None