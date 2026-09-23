"""Serverless function entrypoint for Vercel."""
import os
import sys

# Add project root to sys.path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.app import create_app

app = create_app()
