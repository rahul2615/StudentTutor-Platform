"""
Token-based helpers shared by all API namespaces.
"""

from functools import wraps
from flask import request
from flask_restx import abort
from itsdangerous import URLSafeSerializer

from app.models import User, db

_serializer = None


def _get_serializer():
    global _serializer
    if _serializer is None:
        from flask import current_app
        _serializer = URLSafeSerializer(current_app.config["SECRET_KEY"])
    return _serializer


def generate_api_token(user_id: int) -> str:
    """Create a signed token encoding the user id."""
    return _get_serializer().dumps({"uid": user_id})


def get_current_api_user():
    """Decode the Bearer token and return the User, or None."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    try:
        data = _get_serializer().loads(token)
        return db.session.get(User, data["uid"])
    except Exception:
        return None


def token_required(f):
    """Decorator: require a valid Bearer token."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = get_current_api_user()
        if user is None:
            abort(401, "Valid Bearer token required.")
        return f(*args, user=user, **kwargs)
    return wrapper
