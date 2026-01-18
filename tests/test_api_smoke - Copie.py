from importlib import util
import sys
from fastapi.testclient import TestClient

def test_health_and_predict():
    spec = util.spec_from_file_location("student_api", "api/app.py")
    mod = util.module_from_spec(spec)
    sys.modules["student_api"] = mod
    spec.loader.exec_module(mod)

    client = TestClient(mod.app)
    assert client.get("/health").status_code == 200

    payload = {"G1": 10, "G2": 10, "studytime": 2, "failures": 0, "absences": 0, "source": "mat"}
    r = client.post("/predict", json={"payload": payload, "session_id": "ci"})
    assert r.status_code in (200, 400)
