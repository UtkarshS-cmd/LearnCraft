from __future__ import annotations


class LearnCraftError(Exception):
    def __init__(self, message: str, code: str = "ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class ValidationError(LearnCraftError):
    def __init__(self, message: str):
        super().__init__(message, code="VALIDATION_ERROR", status_code=400)


class AuthError(LearnCraftError):
    def __init__(self, message: str):
        super().__init__(message, code="AUTH_ERROR", status_code=401)


class NotFoundError(LearnCraftError):
    def __init__(self, message: str):
        super().__init__(message, code="NOT_FOUND", status_code=404)
