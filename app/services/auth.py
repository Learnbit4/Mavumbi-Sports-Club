from __future__ import annotations

import bcrypt
from sqlalchemy import select

from ..errors import PermissionDenied, ValidationError
from ..models import User
from . import audit

ROLES = ("admin", "manager", "clerk", "patron")
# Tab-level permissions. admin/manager see everything; clerk runs counter work; patron runs their sports.
PERMISSIONS = {
    "admin": {"members", "store", "events", "equipment", "football", "finance", "reports"},
    "manager": {"members", "store", "events", "equipment", "football", "finance", "reports"},
    "clerk": {"members", "store"},
    "patron": {"members", "events", "equipment", "football"},
}


def can(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())


def require(role: str, permission: str) -> None:
    if not can(role, permission):
        raise PermissionDenied(f"Role '{role}' may not access '{permission}'")


def hash_password(pw: str) -> str:
    if len(pw) < 8:
        raise ValidationError("Password must be at least 8 characters")
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def create_user(session, username: str, password: str, role: str, person_id=None) -> User:
    if role not in ROLES:
        raise ValidationError(f"Role must be one of {ROLES}")
    if not username.strip():
        raise ValidationError("Username required")
    if session.scalar(select(User).where(User.username == username)):
        raise ValidationError("Username already exists")
    u = User(username=username.strip(), password_hash=hash_password(password), role=role, person_id=person_id)
    session.add(u)
    session.flush()
    return u


def authenticate(session, username: str, password: str) -> User | None:
    u = session.scalar(select(User).where(User.username == username, User.active.is_(True)))
    ok = bool(u) and bcrypt.checkpw(password.encode(), u.password_hash.encode())
    audit.log(session, u.id if u else None, "login_ok" if ok else "login_failed", username)
    return u if ok else None
