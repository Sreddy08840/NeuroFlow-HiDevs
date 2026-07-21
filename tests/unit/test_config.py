from backend.config import settings


def test_settings_load():
    assert settings.api_port == 8000
    assert settings.postgres_user == "neuroflow"
    assert "demo-client" in settings.jwt_clients
    assert isinstance(settings.jwt_clients["demo-client"]["scopes"], list)
