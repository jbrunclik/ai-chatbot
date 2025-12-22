import json
import sys
from pathlib import Path

from flask import Flask, Response, render_template, send_from_directory

from src.api.routes import api, auth
from src.config import Config


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        static_folder="../static",
        static_url_path="/static",
        template_folder="templates",
    )

    # Register blueprints
    app.register_blueprint(api)
    app.register_blueprint(auth)

    # Load Vite manifest for production builds
    vite_manifest: dict[str, dict[str, str | list[str]]] = {}
    manifest_path = Path(app.static_folder or "static") / "assets" / ".vite" / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path) as f:
            vite_manifest = json.load(f)

    # Extract app version from manifest (JS bundle hash)
    app_version: str | None = None
    if vite_manifest:
        main_entry = vite_manifest.get("src/main.ts", {})
        js_file = str(main_entry.get("file", ""))
        # Extract hash: "assets/main-y-VVsbiY.js" -> "y-VVsbiY"
        if "-" in js_file and js_file.endswith(".js"):
            app_version = js_file.rsplit("-", 1)[1].replace(".js", "")

    # Store version in app config for access by routes
    app.config["APP_VERSION"] = app_version

    @app.route("/")
    def index() -> str | tuple[str, int]:
        js_file: str | None = None
        css_file: str | None = None

        # In development mode, always use Vite dev server (ignore manifest)
        dev_mode = Config.is_development()

        if not dev_mode:
            # Production: require manifest and use hashed filenames
            if not vite_manifest:
                return "Frontend not built. Run 'make build' first.", 500
            main_entry = vite_manifest.get("src/main.ts", {})
            js_file = str(main_entry.get("file")) if main_entry.get("file") else None
            css_files = main_entry.get("css", [])
            if isinstance(css_files, list) and css_files:
                css_file = str(css_files[0])

        return render_template(
            "index.html",
            js_file=js_file,
            css_file=css_file,
            dev_mode=dev_mode,
            app_version=app_version,
        )

    # Serve static files
    @app.route("/<path:path>")
    def static_files(path: str) -> Response:
        return send_from_directory(app.static_folder or "static", path)

    return app


def main() -> None:
    """Main entry point."""
    # Validate configuration
    errors = Config.validate()
    if errors:
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    app = create_app()
    print(f"Starting AI Chatbot on port {Config.PORT}")
    print(f"Environment: {Config.FLASK_ENV}")
    print(f"Available models: {list(Config.MODELS.keys())}")
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.is_development())


if __name__ == "__main__":
    main()
