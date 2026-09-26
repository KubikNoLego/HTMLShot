"""Runtime settings for the HTTP service, loaded from the environment (.env)."""

from functools import cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
ENV_PREFIX = "HTMLSHOT_"


class Settings(BaseSettings):
    """Runtime configuration settings for the HTTP service.

    Attributes:
        title: The application title displayed in OpenAPI and API metadata.
        host: The network interface address to bind the HTTP server to.
        port: The network port number to listen on (must be between 1 and 65535).
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_prefix=ENV_PREFIX,
        extra="ignore",
        frozen=True,
    )

    title: str = "HTMLShot"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, gt=0, le=65535)


@cache
def load_settings() -> Settings:
    """Load and cache application runtime settings.

    Reads configuration values from environment variables prefixed with
    `HTMLSHOT_` and from an optional `.env` file located at the project root.
    Subsequent calls return the cached singleton instance.

    Returns:
        An immutable Settings instance populated with validated values.
    """
    return Settings()


