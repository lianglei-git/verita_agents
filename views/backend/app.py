"""Flask application for the views agent console."""

from __future__ import annotations

import argparse
import os

from flask import Flask, abort, send_from_directory

from backend.config import DEFAULT_HOST, DEFAULT_PORT, FRONTEND_DIST, MEDIA_TTS_DIR
from backend.routes import api_bp


def create_app(serve_static: bool = False) -> Flask:
    app = Flask(__name__)
    app.register_blueprint(api_bp)

    os.makedirs(MEDIA_TTS_DIR, exist_ok=True)

    @app.get("/media/tts/<path:relpath>")
    def media_tts(relpath: str):
        """Read-only serve of TTS full-mode artifacts (audio.wav, subtitles.json)."""
        root = os.path.realpath(MEDIA_TTS_DIR)
        target = os.path.realpath(os.path.join(MEDIA_TTS_DIR, relpath))
        if not (target == root or target.startswith(root + os.sep)):
            abort(404)
        if not os.path.isfile(target):
            abort(404)
        directory = os.path.dirname(target)
        filename = os.path.basename(target)
        return send_from_directory(directory, filename)

    if serve_static and os.path.isdir(FRONTEND_DIST):

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def spa(path: str):
            if path:
                target = os.path.join(FRONTEND_DIST, path)
                if os.path.isfile(target):
                    return send_from_directory(FRONTEND_DIST, path)
            return send_from_directory(FRONTEND_DIST, "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Views agent console API")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument(
        "--serve-static",
        action="store_true",
        help="Serve frontend/dist as SPA (production mode)",
    )
    args = parser.parse_args()

    app = create_app(serve_static=args.serve_static)
    print(f"API running at http://{args.host}:{args.port}")
    if args.serve_static:
        print(f"Serving static files from {FRONTEND_DIST}")
    print(f"TTS media dir: {MEDIA_TTS_DIR}")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
