from fastapi.testclient import TestClient


def test_host_and_csrf(tmp_path, monkeypatch):
    monkeypatch.setenv("SOILUAT_DATA", str(tmp_path))
    monkeypatch.delenv("SOILUAT_ALLOW_TEST_HOST", raising=False)
    from soiluat.app import app

    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 400
    ok = client.get("/", headers={"Host": "127.0.0.1:8000"})
    assert ok.status_code == 200
    denied = client.post("/backup", headers={"Host": "127.0.0.1:8000"})
    assert denied.status_code == 403
    token = ok.cookies.get("soiluat_csrf")
    assert token
    good = client.post(
        "/backup",
        headers={"Host": "127.0.0.1:8000"},
        data={"csrf_token": token},
    )
    assert good.status_code == 200
    assert good.json()["ok"] is True
    assert not any(k.lower() == "access-control-allow-origin" for k in ok.headers)
