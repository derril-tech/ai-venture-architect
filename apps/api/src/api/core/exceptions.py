"""Custom exceptions for the API."""

from typing import Any, Dict, Optional


class APIException(Exception):
    """Base API exception."""
    
    def __init__(
        self,
        status_code: int,
        error_type: str,
        title: str,
        detail: str,
        headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.status_code = status_code
        self.error_type = error_type
        self.title = title
        self.detail = detail
        self.headers = headers or {}
        super().__init__(detail)


class ValidationError(APIException):
    """Validation error."""
    
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=400,
            error_type="validation_error",
            title="Validation Error",
            detail=detail,
        )


class NotFoundError(APIException):
    """Resource not found error."""
    
    def __init__(self, resource: str, identifier: str) -> None:
        super().__init__(
            status_code=404,
            error_type="not_found",
            title="Resource Not Found",
            detail=f"{resource} with identifier '{identifier}' not found",
        )


class UnauthorizedError(APIException):
    """Unauthorized error."""
    
    def __init__(self, detail: str = "Authentication required") -> None:
        super().__init__(
            status_code=401,
            error_type="unauthorized",
            title="Unauthorized",
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(APIException):
    """Forbidden error."""
    
    def __init__(self, detail: str = "Insufficient permissions") -> None:
        super().__init__(
            status_code=403,
            error_type="forbidden",
            title="Forbidden",
            detail=detail,
        )


class ConflictError(APIException):
    """Conflict error."""
    
    def __init__(self, detail: str) -> None:
        super().__init__(
            status_code=409,
            error_type="conflict",
            title="Conflict",
            detail=detail,
        )


class InternalServerError(APIException):
    """Internal server error."""
    
    def __init__(self, detail: str = "An internal server error occurred") -> None:
        super().__init__(
            status_code=500,
            error_type="internal_server_error",
            title="Internal Server Error",
            detail=detail,
        )
