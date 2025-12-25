import json
import sys
import uuid
from pathlib import Path

from flask import Flask, Response, render_template, request, send_from_directory

from src.api.routes import api, auth
from src.config import Config
from src.utils.logging import get_logger, set_request_id, setup_logging


def create_app() -> Flask:
    """Create and configure the Flask application."""
    # Setup structured logging first
    setup_logging()
    logger = get_logger(__name__)
    logger.info(
        "Flask app created",
        extra={
            "environment": Config.FLASK_ENV,
            "log_level": Config.LOG_LEVEL,
        },
    )

    app = Flask(
        __name__,
        static_folder="../static",
        static_url_path="/static",
        template_folder="templates",
    )

    # Request ID middleware - must be before blueprints
    @app.before_request
    def add_request_id() -> None:
        """Generate and store request ID for correlation."""
        from flask import g

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        set_request_id(request_id)
        g.request_id = request_id

    # Log all requests
    @app.before_request
    def log_request() -> None:
        """Log incoming requests."""
        logger.info(
            "Incoming request",
            extra={
                "method": request.method,
                "path": request.path,
                "remote_addr": request.remote_addr,
                "user_agent": request.headers.get("User-Agent", ""),
            },
        )

    # Log responses
    @app.after_request
    def log_response(response: Response) -> Response:
        """Log outgoing responses."""
        logger.info(
            "Outgoing response",
            extra={
                "method": request.method,
                "path": request.path,
                "status_code": response.status_code,
                "content_length": response.content_length,
            },
        )
        return response

    # Register blueprints
    app.register_blueprint(api)
    app.register_blueprint(auth)

    # Load Vite manifest for production builds
    vite_manifest: dict[str, dict[str, str | list[str]]] = {}
    manifest_path = Path(app.static_folder or "static") / "assets" / ".vite" / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                vite_manifest = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error(
                "Failed to load Vite manifest",
                extra={"path": str(manifest_path), "error": str(e)},
            )

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
        logger.debug("Rendering index page")
        js_file: str | None = None
        css_file: str | None = None

        # In development mode, always use Vite dev server (ignore manifest)
        dev_mode = Config.is_development()

        if not dev_mode:
            # Production: require manifest and use hashed filenames
            if not vite_manifest:
                logger.error("Vite manifest not found in production mode")
                return "Frontend not built. Run 'make build' first.", 500
            main_entry = vite_manifest.get("src/main.ts", {})
            js_file = str(main_entry.get("file")) if main_entry.get("file") else None
            css_files = main_entry.get("css", [])
            if isinstance(css_files, list) and css_files:
                css_file = str(css_files[0])
            logger.debug(
                "Loaded production assets",
                extra={"js_file": js_file, "css_file": css_file, "app_version": app_version},
            )

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
    # Setup logging early
    setup_logging()
    logger = get_logger(__name__)

    # Validate configuration
    errors = Config.validate()
    if errors:
        logger.error("Configuration validation failed", extra={"errors": errors})
        print("Configuration errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    app = create_app()
    logger.info(
        "Starting AI Chatbot",
        extra={
            "port": Config.PORT,
            "environment": Config.FLASK_ENV,
            "models": list(Config.MODELS.keys()),
            "log_level": Config.LOG_LEVEL,
        },
    )
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.is_development())


if __name__ == "__main__":
    main()
