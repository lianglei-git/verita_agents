import os

VIEWS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_DIR = os.path.join(VIEWS_ROOT, "shared")
FRONTEND_DIST = os.path.join(VIEWS_ROOT, "frontend", "dist")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
