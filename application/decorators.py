from functools import wraps
from flask import abort
from flask_login import current_user
import re

def role_required(*roles):
    """Restrict a route to specific user roles (e.g. 'admin', 'staff', 'trekker')."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def is_valid_password(password):
    """Password must be at least 8 characters long and contain at least one digit."""
    if len(password) < 8:
        return False
    if not re.search(r"\d", password):
        return False
    return True