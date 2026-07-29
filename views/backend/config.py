import os

VIEWS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_DIR = os.path.join(VIEWS_ROOT, "shared")
FRONTEND_DIST = os.path.join(VIEWS_ROOT, "frontend", "dist")
# Default TTS full-mode output; overridable via TTS_MEDIA_DIR
MEDIA_TTS_DIR = os.getenv(
    "TTS_MEDIA_DIR",
    os.path.join(VIEWS_ROOT, "backend", "media", "tts"),
).strip() or os.path.join(VIEWS_ROOT, "backend", "media", "tts")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
