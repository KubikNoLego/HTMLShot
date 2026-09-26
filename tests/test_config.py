"""Tests for application runtime configuration settings (pydantic-settings)."""

import pytest
from pydantic import ValidationError

from htmlshot.config import ENV_PREFIX, Settings, load_settings


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure host environment variables do not interfere with settings tests.

    Removes any predefined environment variables prefixed with `HTMLSHOT_`
    for key configuration variables such as TITLE, HOST, and PORT.
    """
    for name in ("TITLE", "HOST", "PORT"):
        monkeypatch.delenv(ENV_PREFIX + name, raising=False)



class TestSettings:
    def test_default_values(self):
        settings = Settings(_env_file=None)
        assert settings.title == "HTMLShot"
        assert settings.host == "127.0.0.1"
        assert settings.port == 8000

    def test_env_prefix_overrides_defaults(self, monkeypatch):
        monkeypatch.setenv(ENV_PREFIX + "PORT", "9001")
        monkeypatch.setenv(ENV_PREFIX + "TITLE", "Тестовый сервис")
        settings = Settings(_env_file=None)
        assert settings.port == 9001
        assert settings.title == "Тестовый сервис"

    def test_foreign_env_vars_ignored(self, monkeypatch):
        monkeypatch.setenv("TITLE", "Чужой заголовок")
        assert Settings(_env_file=None).title == "HTMLShot"

    @pytest.mark.parametrize("port", [0, -1, 65536, 70000])
    def test_port_out_of_range_rejected(self, port):
        with pytest.raises(ValidationError):
            Settings(port=port, _env_file=None)

    def test_invalid_port_in_env_rejected(self, monkeypatch):
        monkeypatch.setenv(ENV_PREFIX + "PORT", "65536")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_non_integer_port_in_env_rejected(self, monkeypatch):
        monkeypatch.setenv(ENV_PREFIX + "PORT", "не-порт")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)

    def test_settings_frozen(self):
        settings = Settings(_env_file=None)
        with pytest.raises(ValidationError):
            settings.title = "Новое имя"  # type: ignore[misc]


class TestLoadSettings:
    def test_returns_settings_instance(self):
        assert isinstance(load_settings(), Settings)

    def test_cached_between_calls(self):
        assert load_settings() is load_settings()

