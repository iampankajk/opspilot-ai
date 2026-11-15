class APIError(Exception):
    """Safe public failure information, never credentials or underlying SQL exceptions."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        clear_cookie: bool = False,
        details: dict | None = None,
        retryable: bool | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.clear_cookie = clear_cookie

        self.details = details or {}
        self.retryable = status == 503 if retryable is None else retryable
