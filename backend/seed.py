"""Seed script — create tables and insert a default admin account + demo data."""

import sys
import os

# Ensure the project root is on sys.path so 'backend' is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app import create_app
from backend.models import db, User
from backend.auth import hash_password


def seed():
    app = create_app()

    with app.app_context():
        db.create_all()
        print('[OK] Database tables created.')

        # Default admin
        admin_email = 'admin@clinic.com'
        if not User.query.filter_by(email=admin_email).first():
            admin = User(
                name='Admin',
                email=admin_email,
                password_hash=hash_password('admin123'),
                role='admin',
                is_active=True,
            )
            db.session.add(admin)
            db.session.commit()
            print(f'[OK] Default admin created: {admin_email} / admin123')
        else:
            print(f'• Admin account already exists: {admin_email}')

        # Seed some demo data
        _seed_demo_data()

        print('\n[OK] Seed complete. Run the server with:')
        print('  python -m backend.app')


def _seed_demo_data():
    """Insert a few demo patients and treatment entries for testing."""
    from datetime import date

    # Check if demo data already exists
    if User.query.filter_by(email='staff1@clinic.com').first():
        print('• Demo data already seeded.')
        return

    # Demo staff member 1 (was doctor)
    staff1 = User(
        name='Dr. Sarah Johnson',
        email='staff1@clinic.com',
        password_hash=hash_password('staff123'),
        role='staff',
        is_active=True,
    )
    db.session.add(staff1)

    # Demo staff member 2 (was receptionist)
    staff2 = User(
        name='Emily Davis',
        email='staff2@clinic.com',
        password_hash=hash_password('staff123'),
        role='staff',
        is_active=True,
    )
    db.session.add(staff2)
    db.session.flush()  # get IDs

    # Demo patients
    from backend.models import Patient, TreatmentEntry

    patients_data = [
        {'name': 'John Smith', 'dob': date(1985, 3, 15), 'gender': 'Male',
         'phone': '+1-555-0101', 'address': '123 Oak Street, Springfield',
         'email': 'john.smith@email.com'},
        {'name': 'Maria Garcia', 'dob': date(1992, 7, 22), 'gender': 'Female',
         'phone': '+1-555-0102', 'address': '456 Elm Avenue, Riverside',
         'additional_phone': '+1-555-0112'},
        {'name': 'Robert Chen', 'dob': date(1978, 11, 8), 'gender': 'Male',
         'phone': '+1-555-0103', 'address': '789 Pine Road, Lakewood'},
        {'name': 'Aisha Patel', 'dob': date(2001, 1, 30), 'gender': 'Female',
         'phone': '+1-555-0104', 'address': '321 Maple Drive, Brookside',
         'email': 'aisha.patel@email.com'},
        {'name': 'James Wilson', 'dob': date(1965, 5, 12), 'gender': 'Male',
         'phone': '+1-555-0105', 'address': '654 Birch Lane, Hillcrest'},
    ]

    for pd in patients_data:
        patient = Patient(registered_by=staff1.id, **pd)
        db.session.add(patient)
    db.session.flush()

    patients = Patient.query.all()

    entries_data = [
        {'patient_id': patients[0].id, 'date_of_treatment': date(2025, 9, 10),
         'consultation_number': 1,
         'treatment_name': 'Type 2 Diabetes Management',
         'medicine': 'Metformin 500mg twice daily',
         'remark': 'Blood sugar levels elevated. Recommended dietary changes and regular exercise.',
         'next_consultation': date(2025, 9, 24),
         'payment': 500.0, 'payment_method': 'Cash',
         'created_by': staff1.id},

        {'patient_id': patients[0].id, 'date_of_treatment': date(2025, 9, 18),
         'consultation_number': 2,
         'treatment_name': 'Hypertension Follow-up',
         'medicine': 'Lisinopril 10mg once daily',
         'remark': 'BP 150/95. Started on medication. Follow-up in 2 weeks.',
         'next_consultation': date(2025, 10, 2),
         'payment': 750.0, 'payment_method': 'UPI',
         'created_by': staff1.id},

        {'patient_id': patients[1].id, 'date_of_treatment': date(2025, 9, 12),
         'consultation_number': 1,
         'treatment_name': 'Seasonal Allergies',
         'medicine': 'Cetirizine 10mg daily, Fluticasone nasal spray',
         'remark': 'Rhinitis and mild conjunctivitis. Symptoms for 3 weeks.',
         'next_consultation': date(2025, 10, 12),
         'payment': 300.0, 'payment_method': 'Card',
         'created_by': staff1.id},

        {'patient_id': patients[2].id, 'date_of_treatment': date(2025, 9, 5),
         'consultation_number': 1,
         'treatment_name': 'Lower Back Pain Treatment',
         'medicine': 'Ibuprofen 400mg TID, Muscle relaxant PRN',
         'remark': 'Acute onset after lifting. No neurological deficits. MRI recommended if persistent.',
         'payment': 1200.0, 'payment_method': 'Insurance',
         'created_by': staff1.id},

        {'patient_id': patients[3].id, 'date_of_treatment': date(2025, 9, 15),
         'consultation_number': 1,
         'treatment_name': 'Upper Respiratory Infection',
         'medicine': 'Rest, fluids, Paracetamol 500mg PRN',
         'remark': 'Viral URI. Symptomatic treatment. Return if fever persists > 5 days.',
         'next_consultation': date(2025, 9, 22),
         'payment': 400.0, 'payment_method': 'Cash',
         'created_by': staff1.id},

        {'patient_id': patients[4].id, 'date_of_treatment': date(2025, 9, 8),
         'consultation_number': 1,
         'treatment_name': 'Osteoarthritis - Knee',
         'medicine': 'Naproxen 250mg BID, Physical therapy referral',
         'remark': 'Bilateral knee pain, worse on stairs. X-ray shows mild joint space narrowing.',
         'next_consultation': date(2025, 10, 8),
         'payment': 900.0, 'payment_method': 'UPI',
         'created_by': staff1.id},
    ]

    for ed in entries_data:
        entry = TreatmentEntry(**ed)
        db.session.add(entry)

    db.session.commit()
    print('[OK] Demo staff accounts, patients, and treatment entries seeded.')
    print('     Staff login: staff1@clinic.com / staff123')
    print('     Staff login: staff2@clinic.com / staff123')


if __name__ == '__main__':
    seed()
