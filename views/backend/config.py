import os

VIEWS_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHARED_DIR = os.path.join(VIEWS_ROOT, "shared")
FRONTEND_DIST = os.path.join(VIEWS_ROOT, "frontend", "dist")

# Media roots for TTS / ASR / future assets (path-based file API is sandboxed here)
MEDIA_ROOT = os.getenv(
    "MEDIA_ROOT",
    os.path.join(VIEWS_ROOT, "backend", "media"),
).strip() or os.path.join(VIEWS_ROOT, "backend", "media")

MEDIA_TTS_DIR = os.getenv(
    "TTS_MEDIA_DIR",
    os.path.join(MEDIA_ROOT, "tts"),
).strip() or os.path.join(MEDIA_ROOT, "tts")

MEDIA_ASR_DIR = os.getenv(
    "ASR_MEDIA_DIR",
    os.path.join(MEDIA_ROOT, "asr"),
).strip() or os.path.join(MEDIA_ROOT, "asr")

MEDIA_IMAGES_DIR = os.getenv(
    "IMAGE_MEDIA_DIR",
    os.path.join(MEDIA_ROOT, "images"),
).strip() or os.path.join(MEDIA_ROOT, "images")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5000
