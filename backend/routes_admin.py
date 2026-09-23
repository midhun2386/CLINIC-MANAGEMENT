"""Admin-only routes — manage staff accounts, delete users, view audit log."""

from flask import Blueprint, request, jsonify, g

from .models import db, User, AuditLog
from .auth import token_required, role_required, hash_password, _log

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


@admin_bp.route('/users', methods=['GET'])
@token_required
@role_required('admin')
def list_users():
    """List all staff accounts."""
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({'users': [u.to_dict() for u in users]})


@admin_bp.route('/users', methods=['POST'])
@token_required
@role_required('admin')
def create_user():
    """Create a new staff account."""
    body = request.get_json(silent=True) or {}
    name = body.get('name', '').strip()
    email = body.get('email', '').strip().lower()
    password = body.get('password', '')
    role = body.get('role', '').strip().lower()

    if not all([name, email, password, role]):
        return jsonify({'error': 'name, email, password, and role are required'}), 400

    if role not in ('admin', 'staff'):
        return jsonify({'error': 'Role must be admin or staff'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Email already in use'}), 409

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        role=role,
    )
    db.session.add(user)
    db.session.commit()

    _log(g.current_user.id, 'USER_CREATED',
         f'new_user_id={user.id} role={role}', request.remote_addr)

    return jsonify({'user': user.to_dict()}), 201


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@token_required
@role_required('admin')
def update_user(user_id):
    """Enable/disable a staff account or update their details."""
    user = User.query.get_or_404(user_id)
    body = request.get_json(silent=True) or {}

    if 'is_active' in body:
        user.is_active = bool(body['is_active'])
    if 'name' in body:
        user.name = body['name'].strip()
    if 'email' in body:
        new_email = body['email'].strip().lower()
        existing = User.query.filter_by(email=new_email).first()
        if existing and existing.id != user.id:
            return jsonify({'error': 'Email already in use'}), 409
        user.email = new_email
    if 'role' in body:
        role = body['role'].strip().lower()
        if role not in ('admin', 'staff'):
            return jsonify({'error': 'Role must be admin or staff'}), 400
        user.role = role
    if 'password' in body and body['password']:
        user.password_hash = hash_password(body['password'])

    db.session.commit()

    _log(g.current_user.id, 'USER_UPDATED',
         f'target_user_id={user.id} active={user.is_active}', request.remote_addr)

    return jsonify({'user': user.to_dict()})


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@token_required
@role_required('admin')
def delete_user(user_id):
    """Delete a staff account (admin only). Cannot delete yourself."""
    if user_id == g.current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400

    user = User.query.get_or_404(user_id)
    user_name = user.name
    db.session.delete(user)
    db.session.commit()

    _log(g.current_user.id, 'USER_DELETED',
         f'deleted_user_id={user_id} name={user_name}', request.remote_addr)

    return jsonify({'message': f'User {user_name} deleted'})


@admin_bp.route('/audit-log', methods=['GET'])
@token_required
@role_required('admin')
def get_audit_log():
    """Return paginated audit log entries."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = min(per_page, 200)  # cap

    pagination = AuditLog.query.order_by(AuditLog.timestamp.desc()) \
        .paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'entries': [e.to_dict() for e in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages,
    })
