"""Flask application factory — creates the app, registers blueprints, serves frontend."""

import os

from flask import Flask, send_from_directory
from flask_cors import CORS

from .config import Config
from .models import db


def create_app():
    # Resolve paths
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    frontend_dir = os.path.join(base_dir, 'frontend')
    upload_dir = os.path.join(base_dir, 'uploads')

    app = Flask(__name__, static_folder=frontend_dir, static_url_path='')
    app.config.from_object(Config)

    # Extensions
    CORS(app)
    db.init_app(app)

    # Ensure upload directories exist
    os.makedirs(os.path.join(upload_dir, 'patients'), exist_ok=True)

    # Create tables on first request (dev convenience)
    with app.app_context():
        db.create_all()

    # ── Register API blueprints ──────────────────────────────────────────
    from .auth import auth_bp
    from .routes_patients import patients_bp
    from .routes_records import records_bp
    from .routes_admin import admin_bp
    from .routes_search import search_bp
    from .routes_chatbot import chatbot_bp
    from .routes_export import export_bp
    from .routes_approvals import approvals_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(records_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(approvals_bp)

    # ── Serve uploaded files ─────────────────────────────────────────────
    @app.route('/uploads/<path:filename>')
    def serve_upload(filename):
        return send_from_directory(upload_dir, filename)

    # ── Serve frontend ───────────────────────────────────────────────────
    @app.route('/')
    def serve_index():
        return send_from_directory(frontend_dir, 'index.html')

    @app.route('/<path:path>')
    def serve_static(path):
        # Serve file if it exists, otherwise fall back to index.html (SPA)
        file_path = os.path.join(frontend_dir, path)
        if os.path.isfile(file_path):
            return send_from_directory(frontend_dir, path)
        return send_from_directory(frontend_dir, 'index.html')

    return app


# Allow running directly: python -m backend.app
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
