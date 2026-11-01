from emporio_agent import config


def test_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("MODEL", "some-model")

    settings = config.load_settings()

    assert settings.api_key == "test-key"
    assert settings.base_url == "http://localhost:11434/v1"
    assert settings.model == "some-model"


def test_empty_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_BASE_URL", "")
    monkeypatch.setenv("MODEL", "")

    settings = config.load_settings()

    assert settings.api_key is None
    assert settings.base_url == config.DEFAULT_BASE_URL
    assert settings.model == config.DEFAULT_MODEL


def test_data_dir_contains_the_challenge_files():
    assert (config.DATA_DIR / "desafio_tecnico_ai_eng - products.csv").exists()
