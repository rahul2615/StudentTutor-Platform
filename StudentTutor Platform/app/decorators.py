"""
Reusable role-based access control decorators.

Replaces scattered `if current_user.role != ...` checks throughout routes
with a clean, composable decorator system.
"""
from functools import wraps
from flask import abort
from flask_login import login_required, current_user


def role_required(*roles):
    """Restrict a view to users whose role is in *roles*.

    Usage::

        @app.route('/admin-only')
        @role_required('admin')
        def secret():
            ...

        @app.route('/staff')
        @role_required('tutor', 'admin')
        def staff_area():
            ...
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator


# ── Convenience shortcuts ────────────────────────────────
def admin_required(f):
    """Shortcut: ``@role_required('admin')``."""
    return role_required('admin')(f)


def tutor_required(f):
    """Shortcut: ``@role_required('tutor')``."""
    return role_required('tutor')(f)


def student_required(f):
    """Shortcut: ``@role_required('student')``."""
    return role_required('student')(f)


def tutor_or_admin(f):
    """Shortcut: ``@role_required('tutor', 'admin')``."""
    return role_required('tutor', 'admin')(f)
