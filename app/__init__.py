from flask import Flask
from .config import Settings

def create_app(settings: Settings | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(SETTINGS=settings or Settings.from_env(require_sms=True), MAX_CONTENT_LENGTH=16384)
    from .routes import routes
    app.register_blueprint(routes)
    return app
