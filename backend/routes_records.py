"""Treatment entry routes — add, list, edit, delete (replaces old medical-record routes)."""

import json
from datetime import datetime

from flask import Blueprint, request, jsonify, g

from .models import db, TreatmentEntry, Patient, ApprovalRequest
from .auth import token_required, role_required, _log

records_bp = Blueprint('records', __name__, url_prefix='/api')


@records_bp.route('/patients/<int:patient_id>/records', methods=['POST'])
@token_required
@role_required('admin', 'staff')
def add_record(patient_id):
    """Create a new treatment entry for a patient."""
    patient = Patient.query.get_or_404(patient_id)
    body = request.get_json(silent=True) or {}

    # Date of treatment
    date_str = body.get('date_of_treatment', '')
    if not date_str:
        date_of_treatment = datetime.utcnow().date()
    else:
        try:
            date_of_treatment = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format (use YYYY-MM-DD)'}), 400

    # Auto-compute consultation number (count of existing + 1), but allow override
    existing_count = TreatmentEntry.query.filter_by(patient_id=patient.id).count()
    consultation_number = body.get('consultation_number', existing_count + 1)
    try:
        consultation_number = int(consultation_number)
    except (ValueError, TypeError):
        consultation_number = existing_count + 1

    # Next consultation date
    next_consultation = None
    next_str = body.get('next_consultation', '').strip() if body.get('next_consultation') else ''
    if next_str:
        try:
            next_consultation = datetime.strptime(next_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid next_consultation date format (use YYYY-MM-DD)'}), 400

    # Payment
    payment = None
    if body.get('payment') is not None and body.get('payment') != '':
        try:
            payment = float(body['payment'])
        except (ValueError, TypeError):
            return jsonify({'error': 'Payment must be a number'}), 400

    entry = TreatmentEntry(
        patient_id=patient.id,
        date_of_treatment=date_of_treatment,
        consultation_number=consultation_number,
        medicine=body.get('medicine', '').strip() or None,
        treatment_name=body.get('treatment_name', '').strip() or None,
        remark=body.get('remark', '').strip() or None,
        next_consultation=next_consultation,
        payment=payment,
        payment_method=body.get('payment_method', '').strip() or None,
        created_by=g.current_user.id,
    )
    db.session.add(entry)
    db.session.commit()

    _log(g.current_user.id, 'TREATMENT_CREATED',
         f'entry_id={entry.id} patient_id={patient.id} consult_no={consultation_number}',
         request.remote_addr)

    return jsonify({'record': entry.to_dict()}), 201


@records_bp.route('/patients/<int:patient_id>/records', methods=['GET'])
@token_required
def list_records(patient_id):
    """List all treatment entries for a patient."""
    patient = Patient.query.get_or_404(patient_id)
    entries = TreatmentEntry.query.filter_by(patient_id=patient.id) \
        .order_by(TreatmentEntry.date_of_treatment.desc()).all()

    _log(g.current_user.id, 'TREATMENTS_VIEWED',
         f'patient_id={patient.id}', request.remote_addr)

    return jsonify({
        'patient_name': patient.name,
        'records': [e.to_dict() for e in entries],
    })


@records_bp.route('/records/<int:record_id>', methods=['PUT'])
@token_required
@role_required('admin', 'staff')
def edit_record(record_id):
    """Edit an existing treatment entry. Admin: direct. Staff: creates approval request."""
    entry = TreatmentEntry.query.get_or_404(record_id)
    body = request.get_json(silent=True) or {}

    # Staff must go through approval workflow
    if g.current_user.role == 'staff':
        approval = ApprovalRequest(
            requested_by=g.current_user.id,
            action_type='EDIT',
            target_type='TREATMENT',
            target_id=record_id,
            proposed_changes=json.dumps(body),
            status='PENDING',
        )
        db.session.add(approval)
        db.session.commit()

        _log(g.current_user.id, 'APPROVAL_REQUESTED',
             f'action=EDIT target=TREATMENT id={record_id}', request.remote_addr)

        return jsonify({
            'message': 'Edit request submitted for admin approval',
            'approval_request': approval.to_dict(),
        }), 202

    # Admin: direct update
    if 'date_of_treatment' in body:
        try:
            entry.date_of_treatment = datetime.strptime(body['date_of_treatment'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format (use YYYY-MM-DD)'}), 400
    if 'consultation_number' in body:
        try:
            entry.consultation_number = int(body['consultation_number'])
        except (ValueError, TypeError):
            return jsonify({'error': 'Consultation number must be an integer'}), 400
    if 'medicine' in body:
        entry.medicine = body['medicine'].strip() or None
    if 'treatment_name' in body:
        entry.treatment_name = body['treatment_name'].strip() or None
    if 'remark' in body:
        entry.remark = body['remark'].strip() or None
    if 'next_consultation' in body:
        if body['next_consultation']:
            try:
                entry.next_consultation = datetime.strptime(body['next_consultation'], '%Y-%m-%d').date()
            except ValueError:
                return jsonify({'error': 'Invalid next_consultation date format'}), 400
        else:
            entry.next_consultation = None
    if 'payment' in body:
        if body['payment'] is not None and body['payment'] != '':
            try:
                entry.payment = float(body['payment'])
            except (ValueError, TypeError):
                return jsonify({'error': 'Payment must be a number'}), 400
        else:
            entry.payment = None
    if 'payment_method' in body:
        entry.payment_method = body['payment_method'].strip() or None

    db.session.commit()

    _log(g.current_user.id, 'TREATMENT_EDITED',
         f'entry_id={entry.id}', request.remote_addr)

    return jsonify({'record': entry.to_dict()})


@records_bp.route('/records/<int:record_id>', methods=['DELETE'])
@token_required
@role_required('admin', 'staff')
def delete_record(record_id):
    """Delete a treatment entry. Admin: direct. Staff: creates approval request."""
    entry = TreatmentEntry.query.get_or_404(record_id)

    # Staff must go through approval workflow
    if g.current_user.role == 'staff':
        approval = ApprovalRequest(
            requested_by=g.current_user.id,
            action_type='DELETE',
            target_type='TREATMENT',
            target_id=record_id,
            status='PENDING',
        )
        db.session.add(approval)
        db.session.commit()

        _log(g.current_user.id, 'APPROVAL_REQUESTED',
             f'action=DELETE target=TREATMENT id={record_id}', request.remote_addr)

        return jsonify({
            'message': 'Delete request submitted for admin approval',
            'approval_request': approval.to_dict(),
        }), 202

    # Admin: direct delete
    db.session.delete(entry)
    db.session.commit()

    _log(g.current_user.id, 'TREATMENT_DELETED',
         f'entry_id={record_id}', request.remote_addr)

    return jsonify({'message': 'Treatment entry deleted'})
