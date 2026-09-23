"""Approval request routes — staff submit, admin review queue."""

import json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g

from .models import db, ApprovalRequest, Patient, TreatmentEntry
from .auth import token_required, role_required, _log

approvals_bp = Blueprint('approvals', __name__, url_prefix='/api/requests')


@approvals_bp.route('', methods=['POST'])
@token_required
@role_required('staff')
def create_request():
    """Staff submits an edit/delete request."""
    body = request.get_json(silent=True) or {}

    action_type = body.get('action_type', '').strip().upper()
    if action_type not in ('EDIT', 'DELETE'):
        return jsonify({'error': 'action_type must be EDIT or DELETE'}), 400

    target_type = body.get('target_type', '').strip().upper()
    if target_type not in ('PATIENT', 'TREATMENT'):
        return jsonify({'error': 'target_type must be PATIENT or TREATMENT'}), 400

    target_id = body.get('target_id')
    if not target_id:
        return jsonify({'error': 'target_id is required'}), 400

    # Verify target exists
    if target_type == 'PATIENT':
        if not Patient.query.get(target_id):
            return jsonify({'error': 'Patient not found'}), 404
    else:
        if not TreatmentEntry.query.get(target_id):
            return jsonify({'error': 'Treatment entry not found'}), 404

    proposed_changes = None
    if action_type == 'EDIT':
        proposed_changes = body.get('proposed_changes')
        if not proposed_changes:
            return jsonify({'error': 'proposed_changes required for EDIT requests'}), 400
        if isinstance(proposed_changes, dict):
            proposed_changes = json.dumps(proposed_changes)

    approval = ApprovalRequest(
        requested_by=g.current_user.id,
        action_type=action_type,
        target_type=target_type,
        target_id=int(target_id),
        proposed_changes=proposed_changes,
        status='PENDING',
    )
    db.session.add(approval)
    db.session.commit()

    _log(g.current_user.id, 'APPROVAL_REQUESTED',
         f'action={action_type} target={target_type} id={target_id}',
         request.remote_addr)

    return jsonify({'approval_request': approval.to_dict()}), 201


@approvals_bp.route('', methods=['GET'])
@token_required
@role_required('admin')
def list_requests():
    """Admin views approval queue. Filter by ?status=pending."""
    status_filter = request.args.get('status', '').strip().upper()

    query = ApprovalRequest.query.order_by(ApprovalRequest.created_at.desc())

    if status_filter and status_filter in ('PENDING', 'APPROVED', 'REJECTED'):
        query = query.filter_by(status=status_filter)

    requests_list = query.all()

    # Enrich with target details
    results = []
    for r in requests_list:
        r_dict = r.to_dict()
        if r.target_type == 'PATIENT':
            p = Patient.query.get(r.target_id)
            r_dict['target_name'] = p.name if p else '(deleted)'
        elif r.target_type == 'TREATMENT':
            t = TreatmentEntry.query.get(r.target_id)
            if t:
                p = Patient.query.get(t.patient_id)
                r_dict['target_name'] = f'{p.name if p else "Unknown"} — Visit #{t.consultation_number}'
            else:
                r_dict['target_name'] = '(deleted)'
        results.append(r_dict)

    return jsonify({'requests': results})


@approvals_bp.route('/<int:request_id>', methods=['PATCH'])
@token_required
@role_required('admin')
def review_request(request_id):
    """Admin approves or rejects a request."""
    approval = ApprovalRequest.query.get_or_404(request_id)

    if approval.status != 'PENDING':
        return jsonify({'error': 'This request has already been reviewed'}), 400

    body = request.get_json(silent=True) or {}
    action = body.get('action', '').strip().lower()

    if action not in ('approve', 'reject'):
        return jsonify({'error': 'action must be "approve" or "reject"'}), 400

    approval.reviewed_by = g.current_user.id
    approval.reviewed_at = datetime.now(timezone.utc)

    if action == 'reject':
        approval.status = 'REJECTED'
        db.session.commit()

        _log(g.current_user.id, 'APPROVAL_REJECTED',
             f'request_id={request_id}', request.remote_addr)

        return jsonify({
            'message': 'Request rejected',
            'approval_request': approval.to_dict(),
        })

    # ── APPROVE: apply the change ──
    approval.status = 'APPROVED'

    if approval.action_type == 'DELETE':
        if approval.target_type == 'PATIENT':
            target = Patient.query.get(approval.target_id)
            if target:
                db.session.delete(target)
                _log(g.current_user.id, 'PATIENT_DELETED',
                     f'patient_id={approval.target_id} (via approval #{request_id})',
                     request.remote_addr)
        elif approval.target_type == 'TREATMENT':
            target = TreatmentEntry.query.get(approval.target_id)
            if target:
                db.session.delete(target)
                _log(g.current_user.id, 'TREATMENT_DELETED',
                     f'entry_id={approval.target_id} (via approval #{request_id})',
                     request.remote_addr)

    elif approval.action_type == 'EDIT':
        changes = {}
        if approval.proposed_changes:
            try:
                changes = json.loads(approval.proposed_changes)
            except (json.JSONDecodeError, TypeError):
                changes = {}

        if approval.target_type == 'PATIENT':
            target = Patient.query.get(approval.target_id)
            if target and changes:
                if 'name' in changes:
                    target.name = changes['name'].strip()
                if 'dob' in changes and changes['dob']:
                    try:
                        target.dob = datetime.strptime(changes['dob'], '%Y-%m-%d').date()
                    except ValueError:
                        pass
                if 'gender' in changes:
                    target.gender = changes['gender'].strip() or target.gender
                if 'phone' in changes:
                    target.phone = changes['phone'].strip() or target.phone
                if 'email' in changes:
                    target.email = changes['email'].strip() or None
                if 'additional_phone' in changes:
                    target.additional_phone = changes['additional_phone'].strip() or None
                if 'address' in changes:
                    target.address = changes['address'].strip() or None
                _log(g.current_user.id, 'PATIENT_UPDATED',
                     f'patient_id={approval.target_id} (via approval #{request_id})',
                     request.remote_addr)

        elif approval.target_type == 'TREATMENT':
            target = TreatmentEntry.query.get(approval.target_id)
            if target and changes:
                if 'date_of_treatment' in changes and changes['date_of_treatment']:
                    try:
                        target.date_of_treatment = datetime.strptime(changes['date_of_treatment'], '%Y-%m-%d').date()
                    except ValueError:
                        pass
                if 'consultation_number' in changes:
                    try:
                        target.consultation_number = int(changes['consultation_number'])
                    except (ValueError, TypeError):
                        pass
                if 'medicine' in changes:
                    target.medicine = changes['medicine'].strip() or None
                if 'treatment_name' in changes:
                    target.treatment_name = changes['treatment_name'].strip() or None
                if 'remark' in changes:
                    target.remark = changes['remark'].strip() or None
                if 'next_consultation' in changes:
                    if changes['next_consultation']:
                        try:
                            target.next_consultation = datetime.strptime(changes['next_consultation'], '%Y-%m-%d').date()
                        except ValueError:
                            pass
                    else:
                        target.next_consultation = None
                if 'payment' in changes:
                    if changes['payment'] is not None and changes['payment'] != '':
                        try:
                            target.payment = float(changes['payment'])
                        except (ValueError, TypeError):
                            pass
                    else:
                        target.payment = None
                if 'payment_method' in changes:
                    target.payment_method = changes['payment_method'].strip() or None
                _log(g.current_user.id, 'TREATMENT_EDITED',
                     f'entry_id={approval.target_id} (via approval #{request_id})',
                     request.remote_addr)

    db.session.commit()

    _log(g.current_user.id, 'APPROVAL_APPROVED',
         f'request_id={request_id}', request.remote_addr)

    return jsonify({
        'message': 'Request approved and changes applied',
        'approval_request': approval.to_dict(),
    })
