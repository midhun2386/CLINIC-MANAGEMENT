import json
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """Staff accounts — admin or staff."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False)          # admin | staff
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    patients_registered = db.relationship('Patient', backref='registered_by_user', lazy=True)
    treatment_entries_created = db.relationship('TreatmentEntry', backref='created_by_user', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class Patient(db.Model):
    """Patient demographics."""
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)              # full_name — required
    dob = db.Column(db.Date, nullable=False)                      # date_of_birth — required
    gender = db.Column(db.String(20), nullable=False)             # required
    phone = db.Column(db.String(30), nullable=False)              # required
    photo_url = db.Column(db.String(500), nullable=True)          # optional
    email = db.Column(db.String(120), nullable=True)              # optional
    additional_phone = db.Column(db.String(30), nullable=True)    # optional
    address = db.Column(db.Text, nullable=True)                   # optional
    registered_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    treatment_entries = db.relationship('TreatmentEntry', backref='patient', lazy=True,
                                        cascade='all, delete-orphan')

    def to_dict(self):
        """Return patient data with treatment entries."""
        data = {
            'id': self.id,
            'name': self.name,
            'dob': self.dob.isoformat() if self.dob else None,
            'gender': self.gender,
            'phone': self.phone,
            'photo_url': self.photo_url,
            'email': self.email,
            'additional_phone': self.additional_phone,
            'address': self.address,
            'registered_by': self.registered_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'treatment_entries': [t.to_dict() for t in self.treatment_entries],
        }
        return data


class TreatmentEntry(db.Model):
    """A single treatment/visit record linked to a patient (replaces MedicalRecord)."""
    __tablename__ = 'treatment_entries'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    date_of_treatment = db.Column(db.Date, nullable=False)
    consultation_number = db.Column(db.Integer, nullable=False)   # auto-increment per patient
    medicine = db.Column(db.Text, nullable=True)
    treatment_name = db.Column(db.Text, nullable=True)            # problem / diagnosis-equivalent
    remark = db.Column(db.Text, nullable=True)
    next_consultation = db.Column(db.Date, nullable=True)
    payment = db.Column(db.Float, nullable=True)                  # amount
    payment_method = db.Column(db.String(50), nullable=True)      # Cash / Card / UPI / Insurance
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'date_of_treatment': self.date_of_treatment.isoformat() if self.date_of_treatment else None,
            'consultation_number': self.consultation_number,
            'medicine': self.medicine,
            'treatment_name': self.treatment_name,
            'remark': self.remark,
            'next_consultation': self.next_consultation.isoformat() if self.next_consultation else None,
            'payment': self.payment,
            'payment_method': self.payment_method,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ApprovalRequest(db.Model):
    """Pending edit/delete request that staff must submit for admin approval."""
    __tablename__ = 'approval_requests'

    id = db.Column(db.Integer, primary_key=True)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action_type = db.Column(db.String(10), nullable=False)        # EDIT | DELETE
    target_type = db.Column(db.String(20), nullable=False)        # PATIENT | TREATMENT
    target_id = db.Column(db.Integer, nullable=False)
    proposed_changes = db.Column(db.Text, nullable=True)          # JSON for EDIT; null for DELETE
    status = db.Column(db.String(10), nullable=False, default='PENDING')  # PENDING | APPROVED | REJECTED
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    requester = db.relationship('User', foreign_keys=[requested_by], backref='approval_requests_made')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='approval_requests_reviewed')

    def to_dict(self):
        changes = None
        if self.proposed_changes:
            try:
                changes = json.loads(self.proposed_changes)
            except (json.JSONDecodeError, TypeError):
                changes = self.proposed_changes
        return {
            'id': self.id,
            'requested_by': self.requested_by,
            'requester_name': self.requester.name if self.requester else None,
            'action_type': self.action_type,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'proposed_changes': changes,
            'status': self.status,
            'reviewed_by': self.reviewed_by,
            'reviewer_name': self.reviewer.name if self.reviewer else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


class AuditLog(db.Model):
    """Immutable log of every sensitive action."""
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    detail = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'detail': self.detail,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }
