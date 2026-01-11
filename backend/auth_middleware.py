"""
Authentication middleware for Supabase JWT verification using JWKS (ECC).
"""
import os
import jwt
from jwt import PyJWKClient
from functools import wraps
from flask import request, jsonify

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json" if SUPABASE_URL else ''

# Cache the JWKS client
_jwks_client = None

def get_jwks_client():
    """Get or create cached JWKS client."""
    global _jwks_client
    if _jwks_client is None and JWKS_URL:
        _jwks_client = PyJWKClient(JWKS_URL, cache_keys=True)
    return _jwks_client


def get_user_from_token():
    """Extract and verify user from Authorization header."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]
    
    # Dev mode: no SUPABASE_URL set
    if not SUPABASE_URL:
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
        jwks_client = get_jwks_client()
        if not jwks_client:
            return None
        
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=['ES256'],
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
    except Exception as e:
        print(f"JWT verification error: {e}")
        return None


def require_auth(f):
    """Decorator requiring valid JWT. Adds current_user to request."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_user_from_token()
        if user is None:
            return jsonify({
                'success': False,
                'error': 'Authentication required',
                'code': 'UNAUTHORIZED'
            }), 401
        request.current_user = user
        return f(*args, **kwargs)
    return decorated


def optional_auth(f):
    """Decorator that optionally extracts user from JWT."""
    @wraps(f)
    def decorated(*args, **kwargs):
        request.current_user = get_user_from_token()
        return f(*args, **kwargs)
    return decorated


def get_user_data_path(user_id):
    """Get path to user's data directory. Creates if needed."""
    base_path = os.path.join(os.path.dirname(__file__), 'user_data')
    user_path = os.path.join(base_path, user_id)
    os.makedirs(user_path, exist_ok=True)
    return user_path


def get_user_csv_path(user_id):
    """Get path to user's CSV file. Returns None if not exists."""
    user_path = get_user_data_path(user_id)
    csv_path = os.path.join(user_path, 'transactions.csv')
    return csv_path if os.path.exists(csv_path) else None