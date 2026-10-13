import logging

from flask import Flask, render_template, request, session, jsonify
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_babel import Babel
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
babel = Babel()
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per minute"],          # generous global default
    storage_uri="memory://",                     # in-process; swap for Redis in production
)
logger = logging.getLogger(__name__)


def get_locale():
    """Resolve the locale for the current request."""
    # 1. Explicit session override (set by language selector)
    lang = session.get("lang")
    if lang:
        return lang
    # 2. Best match from Accept-Language header
    from flask import current_app
    supported = current_app.config.get("SUPPORTED_LANGUAGES", ["en"])
    return request.accept_languages.best_match(supported, default="en")


def create_app():
    app = Flask(__name__, template_folder="templates")
    app.config.from_object("config.Config")

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    babel.init_app(app, locale_selector=get_locale)
    limiter.init_app(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Redirect to login page if not authenticated
    login_manager.login_view = "auth.login"

    # Make get_locale and now() available in all templates
    app.jinja_env.globals["get_locale"] = get_locale
    app.jinja_env.globals["now"] = lambda: datetime.now(timezone.utc).replace(tzinfo=None)

    with app.app_context():
        # Import models so Alembic/Migrate can detect them
        from app import models  # noqa: F401

    # ── Register Blueprints ──────────────────────────────
    from app.routes import auth, student, tutor, admin
    from app.routes.home import home
    from app.routes.engagement import engagement_bp
    from app.routes.ai import ai_bp
    from app.routes.payment import payment_bp
    from app.api import api_bp

    app.register_blueprint(auth.auth_bp, url_prefix="/auth")
    app.register_blueprint(student.student, url_prefix="/student")
    app.register_blueprint(tutor.tutor_bp, url_prefix="/tutor")
    app.register_blueprint(admin.admin_bp, url_prefix="/admin")
    app.register_blueprint(payment_bp)
    app.register_blueprint(engagement_bp)
    app.register_blueprint(home)
    app.register_blueprint(ai_bp)
    app.register_blueprint(api_bp)

    # Exempt Webhook from Rate Limiting
    limiter.exempt(payment_bp)

    # ── Error Handlers ───────────────────────────────────
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404

    @app.errorhandler(429)
    def ratelimit_error(error):
        # Return JSON for API requests, HTML page for browser requests
        if request.path.startswith("/api/"):
            return jsonify({"error": "Rate limit exceeded. Please try again later.",
                            "retry_after": error.description}), 429
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500

    return app


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login session management."""
    from app.models import User  # Import inside function to avoid circular imports
    return db.session.get(User, int(user_id))
