from fastapi.testclient import TestClient

from tests.conftest import create_case


def test_case_lifecycle(client: TestClient) -> None:
    case_id = create_case(client, "State v. Test")
    assert [c["id"] for c in client.get("/api/cases").json()] == [case_id]

    case = client.get(f"/api/cases/{case_id}").json()
    assert case["title"] == "State v. Test"
    assert case["user_side"] == "defence"
    assert case["embed_model"] == "nomic-embed-text"

    assert client.delete(f"/api/cases/{case_id}").status_code == 204
    assert client.get(f"/api/cases/{case_id}").status_code == 404
    assert client.get("/api/cases").json() == []


def test_rejects_invalid_side(client: TestClient) -> None:
    res = client.post("/api/cases", json={"title": "x", "client": "y", "user_side": "judge"})
    assert res.status_code == 422


def test_case_id_cannot_escape_data_dir(client: TestClient) -> None:
    for bad in ["..", "..%2F..%2Fetc", "abc", "0" * 31 + "G"]:
        assert client.get(f"/api/cases/{bad}/documents").status_code == 404
