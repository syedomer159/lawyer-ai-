"""ADR-0001: nothing from one case may be reachable through another case's URLs."""

from fastapi.testclient import TestClient

from tests.conftest import CASE1, CASE2, create_case, upload


def test_cases_cannot_see_each_others_content(client: TestClient) -> None:
    case_a = create_case(client, "A")
    case_b = create_case(client, "B")
    doc_a = upload(client, case_a, CASE1 / "01_FIR_112-2026.pdf")[0]
    upload(client, case_b, CASE2 / "01_FIR_208-2026.pdf")

    # A query that matches case A's FIR word for word, asked in case B.
    hits = client.get(
        f"/api/cases/{case_b}/search",
        params={"q": "Sunita Sharma gold chain snatched Gupta Tea Stall"},
    ).json()
    assert hits, "case B has its own content and should still return something"
    assert all(h["ref"]["filename"] == "01_FIR_208-2026.pdf" for h in hits)
    assert not any("Sunita" in h["text"] for h in hits)

    # Case A's document id is unknown under case B.
    base = f"/api/cases/{case_b}/documents/{doc_a['id']}/pages/1"
    assert client.get(base).status_code == 404
    assert client.get(f"{base}/image").status_code == 404


def test_deleting_a_case_removes_its_files(client: TestClient) -> None:
    case_a = create_case(client, "A")
    case_b = create_case(client, "B")
    upload(client, case_a, CASE1 / "11_Client_Interview_Notes.txt")
    upload(client, case_b, CASE2 / "10_Client_Interview_Notes.txt")

    client.delete(f"/api/cases/{case_a}")
    assert client.get(f"/api/cases/{case_a}/documents").status_code == 404
    assert len(client.get(f"/api/cases/{case_b}/documents").json()) == 1
