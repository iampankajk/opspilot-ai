class APIError(Exception):
    """Safe public failure information, never credentials or underlying SQL exceptions."""

    def __init__(self, status: int, code: str, message: str, *, clear_cookie: bool = False):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.clear_cookie = clear_cookie
