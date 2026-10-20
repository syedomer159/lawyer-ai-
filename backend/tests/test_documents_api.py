from fastapi.testclient import TestClient

from app.retrieval.search import fts_query, rrf
from tests.conftest import CASE1, create_case, upload


def test_upload_ingest_view_and_search(client: TestClient) -> None:
    case_id = create_case(client)
    docs = upload(client, case_id, CASE1 / "01_FIR_112-2026.pdf", CASE1 / "08_CCTV_Still_CAM03.png")
    assert {d["kind"] for d in docs} == {"pdf", "image"}

    # TestClient runs background tasks before returning, so ingestion is done here.
    listed = {d["filename"]: d for d in client.get(f"/api/cases/{case_id}/documents").json()}
    assert all(d["status"] == "ready" for d in listed.values()), listed
    fir = listed["01_FIR_112-2026.pdf"]
    assert fir["n_pages"] == 2

    page = client.get(f"/api/cases/{case_id}/documents/{fir['id']}/pages/2").json()
    assert "No purchase bill" in page["text"] and page["chunks"]
    img = client.get(f"/api/cases/{case_id}/documents/{fir['id']}/pages/1/image")
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"

    hits = client.get(f"/api/cases/{case_id}/search", params={"q": "CCTV camera time"}).json()
    assert hits[0]["ref"]["filename"] == "08_CCTV_Still_CAM03.png"
    assert hits[0]["ref"]["page"] == 1 and hits[0]["ref"]["bbox"] is not None


def test_reupload_is_deduplicated(client: TestClient) -> None:
    case_id = create_case(client)
    first = upload(client, case_id, CASE1 / "11_Client_Interview_Notes.txt")
    again = upload(client, case_id, CASE1 / "11_Client_Interview_Notes.txt")
    assert first[0]["id"] == again[0]["id"]
    assert len(client.get(f"/api/cases/{case_id}/documents").json()) == 1


def test_rejects_unsupported_type(client: TestClient) -> None:
    case_id = create_case(client)
    res = client.post(f"/api/cases/{case_id}/documents", files=[("files", ("run.exe", b"MZ"))])
    assert res.status_code == 415


def test_rrf_rewards_agreement() -> None:
    fused = rrf([[1, 2, 3], [3, 1, 4]])
    assert [cid for cid, _ in fused][:2] == [1, 3]


def test_fts_query_quotes_words_so_operators_are_inert() -> None:
    q = fts_query('chain" OR NEAR(x) what was the time?')
    assert q == '"chain" OR "or" OR "near" OR "x" OR "time"'
