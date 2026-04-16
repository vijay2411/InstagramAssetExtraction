from __future__ import annotations
from typing import Protocol

class UserContext(Protocol):
    def user_id(self) -> str: ...

class DefaultUserContext:
    """Phase 1: hardcoded single user. Phase 2 swaps for JWT-decoded impl."""
    def user_id(self) -> str:
        return "default"
