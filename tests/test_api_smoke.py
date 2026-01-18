import sys
from importlib import util
from fastapi.testclient import TestClient

def test_health():
    """Test que l'API démarre et /health répond."""
    spec = util.spec_from_file_location("student_api", "api/app.py")
    mod = util.module_from_spec(spec)
    sys.modules["student_api"] = mod
    spec.loader.exec_module(mod)
    client = TestClient(mod.app)
    
    # Test /health seulement (pas besoin des modèles)
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "models" in data
