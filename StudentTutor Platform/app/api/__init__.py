"""
Public REST API — Flask-RESTX with Swagger docs at /api/docs.

Token authentication via itsdangerous signed tokens.
"""

from flask import Blueprint
from flask_restx import Api

api_bp = Blueprint("api", __name__, url_prefix="/api")

api = Api(
    api_bp,
    version="1.0",
    title="EduConnect API",
    description="Public REST API for the EduConnect Student Tutor Platform. "
                "Supports course browsing, enrollment, and user management.",
    doc="/docs",
)

# Import & register namespaces AFTER Api is created to avoid circular imports
from app.api.auth_api import ns as auth_ns      # noqa: E402
from app.api.courses_api import ns as courses_ns  # noqa: E402
from app.api.enrollments_api import ns as enrollments_ns  # noqa: E402
from app.api.users_api import ns as users_ns      # noqa: E402

api.add_namespace(auth_ns)
api.add_namespace(courses_ns)
api.add_namespace(enrollments_ns)
api.add_namespace(users_ns)
