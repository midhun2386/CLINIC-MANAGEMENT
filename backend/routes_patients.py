"""Patient management routes — register, list, detail, edit, delete, photo upload."""

import os
import json
from datetime import datetime

from flask import Blueprint, request, jsonify, g, current_app
from werkzeug.utils import secure_filename

from .models import db, Patient, ApprovalRequest, AuditLog
from .auth import token_required, role_required, _log

patients_bp = Blueprint('patients', __name__, url_prefix='/api/patients')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@patients_bp.route('', methods=['POST'])
@token_required
@role_required('admin', 'staff')
def register_patient():
    """Register a new patient."""
    body = request.get_json(silent=True) or {}

    # Required fields
    name = body.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Patient name is required'}), 400

    dob_str = body.get('dob', '').strip()
    if not dob_str:
        return jsonify({'error': 'Date of birth is required'}), 400
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format (use YYYY-MM-DD)'}), 400

    phone = body.get('phone', '').strip()
    if not phone:
        return jsonify({'error': 'Phone number is required'}), 400

    gender = body.get('gender', '').strip()
    if not gender:
        return jsonify({'error': 'Gender is required'}), 400

    patient = Patient(
        name=name,
        dob=dob,
        gender=gender,
        phone=phone,
        email=body.get('email', '').strip() or None,
        additional_phone=body.get('additional_phone', '').strip() or None,
        address=body.get('address', '').strip() or None,
        registered_by=g.current_user.id,
    )
    db.session.add(patient)
    db.session.commit()

    _log(g.current_user.id, 'PATIENT_REGISTERED',
         f'patient_id={patient.id} name={patient.name}', request.remote_addr)

    return jsonify({'patient': patient.to_dict()}), 201


@patients_bp.route('', methods=['GET'])
@token_required
def list_patients():
    """List patients, optionally filtered by name search query ``?q=``."""
    q = request.args.get('q', '').strip()
    query = Patient.query.order_by(Patient.created_at.desc())

    if q:
        query = query.filter(Patient.name.ilike(f'%{q}%'))

    patients = query.all()
    return jsonify({
        'patients': [p.to_dict() for p in patients],
    })


@patients_bp.route('/<int:patient_id>', methods=['GET'])
@token_required
def get_patient(patient_id):
    """Return a single patient's detail."""
    patient = Patient.query.get_or_404(patient_id)

    _log(g.current_user.id, 'PATIENT_VIEWED',
         f'patient_id={patient.id}', request.remote_addr)

    return jsonify({'patient': patient.to_dict()})


@patients_bp.route('/<int:patient_id>', methods=['PUT'])
@token_required
@role_required('admin', 'staff')
def update_patient(patient_id):
    """Update patient demographics. Admin: direct. Staff: creates approval request."""
    patient = Patient.query.get_or_404(patient_id)
    body = request.get_json(silent=True) or {}

    # Staff must go through approval workflow
    if g.current_user.role == 'staff':
        approval = ApprovalRequest(
            requested_by=g.current_user.id,
            action_type='EDIT',
            target_type='PATIENT',
            target_id=patient_id,
            proposed_changes=json.dumps(body),
            status='PENDING',
        )
        db.session.add(approval)
        db.session.commit()

        _log(g.current_user.id, 'APPROVAL_REQUESTED',
             f'action=EDIT target=PATIENT id={patient_id}', request.remote_addr)

        return jsonify({
            'message': 'Edit request submitted for admin approval',
            'approval_request': approval.to_dict(),
        }), 202

    # Admin: direct update
    if 'name' in body:
        patient.name = body['name'].strip()
    if 'dob' in body:
        try:
            patient.dob = datetime.strptime(body['dob'], '%Y-%m-%d').date() if body['dob'] else patient.dob
        except ValueError:
            return jsonify({'error': 'Invalid date format (use YYYY-MM-DD)'}), 400
    if 'gender' in body:
        patient.gender = body['gender'].strip() or patient.gender
    if 'phone' in body:
        patient.phone = body['phone'].strip() or patient.phone
    if 'email' in body:
        patient.email = body['email'].strip() or None
    if 'additional_phone' in body:
        patient.additional_phone = body['additional_phone'].strip() or None
    if 'address' in body:
        patient.address = body['address'].strip() or None

    db.session.commit()

    _log(g.current_user.id, 'PATIENT_UPDATED',
         f'patient_id={patient.id}', request.remote_addr)

    return jsonify({'patient': patient.to_dict()})


@patients_bp.route('/<int:patient_id>', methods=['DELETE'])
@token_required
@role_required('admin', 'staff')
def delete_patient(patient_id):
    """Delete a patient. Admin: direct. Staff: creates approval request."""
    patient = Patient.query.get_or_404(patient_id)

    # Staff must go through approval workflow
    if g.current_user.role == 'staff':
        approval = ApprovalRequest(
            requested_by=g.current_user.id,
            action_type='DELETE',
            target_type='PATIENT',
            target_id=patient_id,
            status='PENDING',
        )
        db.session.add(approval)
        db.session.commit()

        _log(g.current_user.id, 'APPROVAL_REQUESTED',
             f'action=DELETE target=PATIENT id={patient_id}', request.remote_addr)

        return jsonify({
            'message': 'Delete request submitted for admin approval',
            'approval_request': approval.to_dict(),
        }), 202

    # Admin: direct delete
    patient_name = patient.name
    db.session.delete(patient)
    db.session.commit()

    _log(g.current_user.id, 'PATIENT_DELETED',
         f'patient_id={patient_id} name={patient_name}', request.remote_addr)

    return jsonify({'message': f'Patient {patient_name} deleted'})


@patients_bp.route('/<int:patient_id>/photo', methods=['POST'])
@token_required
@role_required('admin', 'staff')
def upload_photo(patient_id):
    """Upload a patient photo."""
    patient = Patient.query.get_or_404(patient_id)

    if 'photo' not in request.files:
        return jsonify({'error': 'No photo file provided'}), 400

    file = request.files['photo']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    if not _allowed_file(file.filename):
        return jsonify({'error': 'File type not allowed. Use: png, jpg, jpeg, gif, webp'}), 400

    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'patients')
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f'patient_{patient_id}.{ext}')
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    # Store relative URL
    patient.photo_url = f'/uploads/patients/{filename}'
    db.session.commit()

    _log(g.current_user.id, 'PATIENT_PHOTO_UPLOADED',
         f'patient_id={patient_id}', request.remote_addr)

    return jsonify({'photo_url': patient.photo_url})
