from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    demo_user_email: str = Field(
        default="alex.kim@acme.com", validation_alias="DEMO_USER_EMAIL"
    )
    db_url: str = Field(default="sqlite:///./hr_demo.db", validation_alias="DB_URL")
    turso_database_url: str = Field(default="", validation_alias="TURSO_DATABASE_URL")
    turso_auth_token: str = Field(default="", validation_alias="TURSO_AUTH_TOKEN")
    allowed_test_user_emails: str = Field(
        default="", validation_alias="ALLOWED_TEST_USER_EMAILS"
    )

    llm_provider: str = Field(
        default="openai_compatible", validation_alias="LLM_PROVIDER"
    )
    llm_api_key: str = Field(default="", validation_alias="LLM_API_KEY")
    llm_base_url: str = Field(default="", validation_alias="LLM_BASE_URL")
    llm_model: str = Field(default="gpt-4o-mini", validation_alias="LLM_MODEL")

    # API Server settings
    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")

    # Langfuse tracing settings
    langfuse_enabled: bool = Field(default=False, validation_alias="LANGFUSE_ENABLED")
    langfuse_public_key: str = Field(default="", validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: str = Field(default="", validation_alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com", validation_alias="LANGFUSE_HOST"
    )


settings = Settings()


_langfuse_handler = None
_langfuse_client = None


def get_langfuse_handler():
    """Create a Langfuse CallbackHandler for LangChain/LangGraph tracing.

    Returns None when Langfuse is not configured.

    Note: Langfuse v3+ uses environment variables for authentication.
    Set LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, and LANGFUSE_HOST.
    """
    global _langfuse_handler
    if _langfuse_handler is not None:
        return _langfuse_handler

    if not settings.langfuse_enabled:
        return None
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    import os
    try:
        from langfuse.langchain import CallbackHandler
    except ModuleNotFoundError:
        return None

    # Langfuse v3+ reads from environment variables
    # Set them temporarily if not already set
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

    _langfuse_handler = CallbackHandler()
    return _langfuse_handler


def get_langfuse_client():
    """Create a Langfuse client for custom scoring/events.

    Returns None when Langfuse is not configured.
    """
    global _langfuse_client
    if _langfuse_client is not None:
        return _langfuse_client

    if not settings.langfuse_enabled:
        return None
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None

    import os
    try:
        from langfuse import Langfuse
    except ModuleNotFoundError:
        return None

    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key)
    os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key)
    os.environ.setdefault("LANGFUSE_HOST", settings.langfuse_host)

    _langfuse_client = Langfuse()
    return _langfuse_client
