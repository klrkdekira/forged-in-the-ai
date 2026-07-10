from pathlib import Path

from app.settings import Settings, get_settings


def test_reads_data_dir_and_llm_config_from_env(monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", "/tmp/some-data-dir")
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "llama3.1")
    monkeypatch.setenv("LLM_API_KEY", "secret")

    settings = Settings()

    assert settings.data_dir == Path("/tmp/some-data-dir")
    assert settings.llm_base_url == "http://localhost:11434/v1"
    assert settings.llm_model == "llama3.1"
    assert settings.llm_api_key == "secret"


def test_defaults_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)

    settings = Settings()

    assert settings.data_dir == Path("./data")
    assert settings.llm_base_url is None


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
