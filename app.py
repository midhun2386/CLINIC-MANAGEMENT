"""Root entrypoint for Vercel and local execution."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
