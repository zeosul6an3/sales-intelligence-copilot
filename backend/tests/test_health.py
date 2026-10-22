from fastapi.testclient import TestClient

from sic import main
from sic.config import get_settings


def test_default_settings_bind_to_localhost_only(monkeypatch):
    for name in ("SIC_HOST", "SIC_PORT", "SIC_OLLAMA_URL"):
        monkeypatch.delenv(name, raising=False)
    settings = get_settings()
    assert settings.host == "127.0.0.1"
    assert settings.ollama_url == "http://127.0.0.1:11434"


def test_health_reports_ok_when_ollama_is_down(monkeypatch):
    monkeypatch.setattr(
        main, "check_ollama", lambda url: {"reachable": False, "error": "ConnectError"}
    )
    client = TestClient(main.create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ollama"]["reachable"] is False


def test_check_ollama_never_raises_on_unreachable_server():
    # Port 9 (discard) on localhost is not an Ollama server; the check must
    # return a structured result instead of raising.
    result = main.check_ollama("http://127.0.0.1:9", timeout_s=0.5)
    assert result["reachable"] is False
