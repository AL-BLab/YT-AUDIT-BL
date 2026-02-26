"""Flask entrypoint for the Brainlabs coworker audit app."""

from __future__ import annotations

from flask import Flask, g
from werkzeug.middleware.proxy_fix import ProxyFix

from web.config import AppConfig
from web.db import init_db
from web.routes.api import api_bp
from web.routes.internal import internal_bp
from web.routes.pages import pages_bp



def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")

    config = AppConfig.from_env()
    app.config.update(config.to_flask_config())

    init_db(app)

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(internal_bp)

    @app.context_processor
    def inject_globals():
        return {
            "app_name": "Brainlabs YouTube Audit",
            "env_name": app.config.get("APP_ENV", "development"),
            "current_user": getattr(g, "current_user", None),
        }

    @app.template_filter("status_class")
    def status_class(value: str) -> str:
        mapping = {
            "queued": "queued",
            "running": "running",
            "completed": "completed",
            "failed": "failed",
        }
        return mapping.get((value or "").lower(), "default")

    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=app.config.get("APP_ENV") != "production")
