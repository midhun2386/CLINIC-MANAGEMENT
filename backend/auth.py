"""Authentication & authorization helpers: JWT creation, decorators, login/logout routes."""

import functools
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import Blueprint, request, jsonify, g, current_app

from .models import db, User, AuditLog

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def check_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_token(user: User) -> str:
    """Issue a signed JWT containing user_id and role."""
    payload = {
        'user_id': user.id,
        'role': user.role,
        'exp': datetime.now(timezone.utc) + timedelta(
            minutes=current_app.config['JWT_EXPIRY_MINUTES']
        ),
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def _log(user_id, action, detail='', ip=''):
    """Write one row to the audit log."""
    entry = AuditLog(user_id=user_id, action=action, detail=detail, ip_address=ip)
    db.session.add(entry)
    db.session.commit()


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def token_required(f):
    """Reject requests without a valid JWT.  Sets ``g.current_user``."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]

        if not token:
            return jsonify({'error': 'Token missing'}), 401

        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        user = User.query.get(data['user_id'])
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or disabled'}), 401

        g.current_user = user
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """Allow only users whose role is in *roles*."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if g.current_user.role not in roles:
                _log(g.current_user.id, 'ACCESS_DENIED',
                     f'Attempted {request.method} {request.path}',
                     request.remote_addr)
                return jsonify({'error': 'Forbidden'}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['POST'])
def login():
    body = request.get_json(silent=True) or {}
    email = body.get('email', '').strip().lower()
    password = body.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not check_password(password, user.password_hash):
        # Log failed attempt (user_id may be None if email not found)
        _log(user.id if user else None, 'LOGIN_FAILED',
             f'email={email}', request.remote_addr)
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.is_active:
        return jsonify({'error': 'Account disabled — contact admin'}), 403

    token = create_token(user)
    _log(user.id, 'LOGIN', f'Successful login', request.remote_addr)

    return jsonify({
        'token': token,
        'user': user.to_dict(),
    })


@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout():
    _log(g.current_user.id, 'LOGOUT', '', request.remote_addr)
    return jsonify({'message': 'Logged out'})


@auth_bp.route('/me', methods=['GET'])
@token_required
def me():
    return jsonify({'user': g.current_user.to_dict()})
