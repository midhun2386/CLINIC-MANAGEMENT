"""Unified search across patients and treatment entries."""

from flask import Blueprint, request, jsonify, g

from .models import db, Patient, TreatmentEntry
from .auth import token_required, _log

search_bp = Blueprint('search', __name__, url_prefix='/api/search')


@search_bp.route('', methods=['GET'])
@token_required
def search():
    """
    Search patients and treatment entries.

    Query params:
        q          — free-text search (patient name, treatment name, medicine, remark)
        date_from  — filter entries from this date (YYYY-MM-DD)
        date_to    — filter entries up to this date (YYYY-MM-DD)
    """
    q = request.args.get('q', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    results = {
        'patients': [],
        'records': [],
    }

    if q:
        # Search patients by name, phone, email
        patients = Patient.query.filter(
            db.or_(
                Patient.name.ilike(f'%{q}%'),
                Patient.phone.ilike(f'%{q}%'),
                Patient.email.ilike(f'%{q}%'),
            )
        ).all()
        results['patients'] = [p.to_dict() for p in patients]

        # Search treatment entries by treatment_name, medicine, remark
        record_query = TreatmentEntry.query.filter(
            db.or_(
                TreatmentEntry.treatment_name.ilike(f'%{q}%'),
                TreatmentEntry.medicine.ilike(f'%{q}%'),
                TreatmentEntry.remark.ilike(f'%{q}%'),
            )
        )

        if date_from:
            record_query = record_query.filter(TreatmentEntry.date_of_treatment >= date_from)
        if date_to:
            record_query = record_query.filter(TreatmentEntry.date_of_treatment <= date_to)

        records = record_query.order_by(TreatmentEntry.date_of_treatment.desc()).all()
        results['records'] = [r.to_dict() for r in records]

        # Enrich records with patient name
        patient_ids = {r.patient_id for r in records}
        if patient_ids:
            p_map = {p.id: p.name for p in Patient.query.filter(Patient.id.in_(patient_ids)).all()}
            for rec in results['records']:
                rec['patient_name'] = p_map.get(rec['patient_id'], 'Unknown')

    _log(g.current_user.id, 'SEARCH',
         f'q="{q}" date_from={date_from} date_to={date_to}', request.remote_addr)

    return jsonify(results)
