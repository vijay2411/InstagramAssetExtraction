from app.core.user_context import UserContext, DefaultUserContext

def test_default_user_context_returns_default_user():
    ctx = DefaultUserContext()
    assert ctx.user_id() == "default"

def test_user_context_is_protocol():
    class CustomUC:
        def user_id(self) -> str:
            return "alice"
    uc: UserContext = CustomUC()
    assert uc.user_id() == "alice"
