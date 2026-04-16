class StageError(Exception):
    """Raised by a pipeline stage when it cannot complete."""
    def __init__(self, message: str, retriable: bool = True):
        super().__init__(message)
        self.message = message
        self.retriable = retriable
