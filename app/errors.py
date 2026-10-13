class ClubError(Exception):
    """Base class for expected business-rule failures (shown to the user as warnings)."""

class ValidationError(ClubError): pass
class NotFound(ClubError): pass
class StockError(ClubError): pass
class PermissionDenied(ClubError): pass
