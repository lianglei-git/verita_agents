"""Flask application for the views agent console."""

from __future__ import annotations

import argparse
import os

from flask import Flask, send_from_directory

from backend.config import DEFAULT_HOST, DEFAULT_PORT, FRONTEND_DIST
from backend.routes import api_bp


def create_app(serve_static: bool = False) -> Flask:
    app = Flask(__name__)
    app.register_blueprint(api_bp)

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
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
