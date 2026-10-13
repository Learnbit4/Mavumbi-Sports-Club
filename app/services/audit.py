from ..models import AuditLog


def log(session, user_id, action: str, detail: str = "") -> None:
    session.add(AuditLog(user_id=user_id, action=action, detail=detail[:500]))
