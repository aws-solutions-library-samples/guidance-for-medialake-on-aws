"""Custom exceptions for MediaLake Lambda functions."""


class ForbiddenError(Exception):
    """
    Exception for 403 Forbidden responses.

    Raised when a user is authenticated but not authorized to perform an action.
    Compatible with Lambda Powertools event handler exception handling.
    """

    def __init__(self, message: str = "Forbidden"):
        self.message = message
        self.status_code = 403
        super().__init__(self.message)
