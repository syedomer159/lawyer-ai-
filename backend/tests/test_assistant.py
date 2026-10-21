from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents.assistant import case_tools
from app.store.case_store import CaseStore
from tests.conftest import CASE1, CASE2, FakeEmbedder, create_case, upload


def test_ask_stores_conversation_offline(client: TestClient) -> None:
    case_id = create_case(client)
    upload(client, case_id, CASE1 / "03_Statement_Ramesh_Kumar_PW2.pdf")
    res = client.post(f"/api/cases/{case_id}/assistant", json={"text": "What did Ramesh see?"})
    assert res.status_code == 200, res.text
    messages = res.json()
    assert [m["role"] for m in messages] == ["user", "assistant"]
    # The offline model cites made-up chunks: they must not surface as sources.
    assert all(
        c["ref"]["filename"] == "03_Statement_Ramesh_Kumar_PW2.pdf"
        for m in messages
        for c in m["citations"]
    )
    assert client.get(f"/api/cases/{case_id}/assistant").json() == messages


@pytest.mark.anyio
async def test_assistant_tools_only_see_their_own_case(client: TestClient, tmp_path: Path) -> None:
    case_a, case_b = create_case(client, "A"), create_case(client, "B")
    upload(client, case_a, CASE1 / "01_FIR_112-2026.pdf")
    upload(client, case_b, CASE2 / "01_FIR_208-2026.pdf")
    store = CaseStore(tmp_path / "cases" / case_b)
    try:
        search_case = case_tools(store, FakeEmbedder())[0]
        result = await search_case("Sunita Sharma gold chain snatched")
    finally:
        store.close()
    assert "Sunita" not in result and "208/2026" in result
