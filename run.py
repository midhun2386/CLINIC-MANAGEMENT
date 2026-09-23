"""Entry point for running the Flask app directly: python run.py"""
from backend.app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
