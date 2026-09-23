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

    def __init__(self, name=None, email=None, password_hash=None, role=None, is_active=True, **kwargs):
        super().__init__(**kwargs)
        if name is not None:
            self.name = name
        if email is not None:
            self.email = email
        if password_hash is not None:
            self.password_hash = password_hash
        if role is not None:
            self.role = role
        if is_active is not None:
            self.is_active = is_active

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

    def __init__(self, name=None, dob=None, gender=None, phone=None, photo_url=None, email=None,
                 additional_phone=None, address=None, registered_by=None, **kwargs):
        super().__init__(**kwargs)
        if name is not None:
            self.name = name
        if dob is not None:
            self.dob = dob
        if gender is not None:
            self.gender = gender
        if phone is not None:
            self.phone = phone
        if photo_url is not None:
            self.photo_url = photo_url
        if email is not None:
            self.email = email
        if additional_phone is not None:
            self.additional_phone = additional_phone
        if address is not None:
            self.address = address
        if registered_by is not None:
            self.registered_by = registered_by

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

    def __init__(self, patient_id=None, date_of_treatment=None, consultation_number=None, medicine=None,
                 treatment_name=None, remark=None, next_consultation=None, payment=None,
                 payment_method=None, created_by=None, **kwargs):
        super().__init__(**kwargs)
        if patient_id is not None:
            self.patient_id = patient_id
        if date_of_treatment is not None:
            self.date_of_treatment = date_of_treatment
        if consultation_number is not None:
            self.consultation_number = consultation_number
        if medicine is not None:
            self.medicine = medicine
        if treatment_name is not None:
            self.treatment_name = treatment_name
        if remark is not None:
            self.remark = remark
        if next_consultation is not None:
            self.next_consultation = next_consultation
        if payment is not None:
            self.payment = payment
        if payment_method is not None:
            self.payment_method = payment_method
        if created_by is not None:
            self.created_by = created_by

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

    def __init__(self, requested_by=None, action_type=None, target_type=None, target_id=None,
                 proposed_changes=None, status='PENDING', reviewed_by=None, **kwargs):
        super().__init__(**kwargs)
        if requested_by is not None:
            self.requested_by = requested_by
        if action_type is not None:
            self.action_type = action_type
        if target_type is not None:
            self.target_type = target_type
        if target_id is not None:
            self.target_id = target_id
        if proposed_changes is not None:
            self.proposed_changes = proposed_changes
        if status is not None:
            self.status = status
        if reviewed_by is not None:
            self.reviewed_by = reviewed_by

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

    def __init__(self, user_id=None, action=None, detail=None, ip_address=None, **kwargs):
        super().__init__(**kwargs)
        if user_id is not None:
            self.user_id = user_id
        if action is not None:
            self.action = action
        if detail is not None:
            self.detail = detail
        if ip_address is not None:
            self.ip_address = ip_address

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'detail': self.detail,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
        }
