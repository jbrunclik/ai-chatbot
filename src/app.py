import sys

from flask import Flask, Response, send_from_directory

from src.api.routes import api, auth
from src.config import Config


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    # Register blueprints
    app.register_blueprint(api)
    app.register_blueprint(auth)

    # Serve index.html at root with version for cache busting
    @app.route("/")
    def index() -> Response:
        static_folder = app.static_folder or "static"
        with open(f"{static_folder}/index.html") as f:
            html = f.read()
        # Inject version query param for cache busting
        html = html.replace('.css"', f'.css?v={Config.VERSION}"')
        html = html.replace('.js"', f'.js?v={Config.VERSION}"')
        return Response(html, mimetype="text/html")

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
    print(f"Local mode: {Config.LOCAL_MODE}")
    print(f"Available models: {list(Config.MODELS.keys())}")
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)


if __name__ == "__main__":
    main()
