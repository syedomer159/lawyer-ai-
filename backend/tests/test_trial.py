from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.trial.phases import awaiting_user, next_state
from app.agents.trial.roles import witness_statements
from app.contracts.trial import TrialPhase
from app.store.case_store import CaseStore
from tests.conftest import CASE1, create_case, upload


def test_phase_order_over_two_witnesses() -> None:
    state: tuple[TrialPhase, int] = ("opening", 0)
    seen: list[tuple[TrialPhase, int]] = []
    while state[0] != "closed":
        seen.append(state)
        state = next_state(state[0], state[1], n_witnesses=2)
    assert seen == [
        ("opening", 0),
        ("chief", 0),
        ("cross", 0),
        ("chief", 1),
        ("cross", 1),
        ("final", 0),
        ("judgment", 0),
    ]


def test_lawyer_examines_only_on_their_side() -> None:
    assert awaiting_user("cross", "defence", []) and not awaiting_user("chief", "defence", [])
    assert awaiting_user("chief", "prosecution", []) and not awaiting_user(
        "cross", "prosecution", []
    )


def test_witness_sees_only_their_own_documents(client: TestClient, tmp_path: Path) -> None:
    case_id = create_case(client)
    upload(
        client, case_id, CASE1 / "03_Statement_Ramesh_Kumar_PW2.pdf", CASE1 / "10_MLC_Report.pdf"
    )
    store = CaseStore(tmp_path / "cases" / case_id)
    try:
        known = witness_statements(store, "Ramesh Kumar")
    finally:
        store.close()
    assert "red jacket" in known
    assert "No external injury" not in known  # the MLC is not his document


def test_full_mock_trial_offline(client: TestClient) -> None:
    case_id = create_case(client)  # user is defence counsel
    upload(client, case_id, CASE1 / "03_Statement_Ramesh_Kumar_PW2.pdf")
    base = f"/api/cases/{case_id}/trial/sessions"

    res = client.post(base, json={"witnesses": [{"name": "Ramesh Kumar", "role": "witness"}]})
    assert res.status_code == 201, res.text
    s = res.json()
    sid = s["id"]
    # The AI prosecutor opened and examined in chief; now it is the defence's cross-examination.
    assert s["phase"] == "cross" and s["awaiting_user"]
    assert [t["speaker"] for t in s["turns"]][:2] == ["judge", "counsel"]
    assert sum(t["kind"] == "answer" for t in s["turns"]) == 2

    s = client.post(
        f"{base}/{sid}/turns", json={"kind": "question", "text": "What time was it?"}
    ).json()
    assert s["turns"][-1]["speaker"] in ("witness", "judge")  # answered, or objection ruled on
    assert (
        client.post(f"{base}/{sid}/turns", json={"kind": "argument", "text": "x"}).status_code
        == 409
    )

    s = client.post(f"{base}/{sid}/advance").json()
    assert s["phase"] == "final" and s["turns"][-1]["speaker"] == "counsel"  # prosecution argued
    assert client.post(f"{base}/{sid}/advance").status_code == 409  # must argue first
    client.post(f"{base}/{sid}/turns", json={"kind": "argument", "text": "Not proved."})
    s = client.post(f"{base}/{sid}/advance").json()
    assert s["phase"] == "closed" and s["turns"][-1]["speaker"] == "judge"

    s = client.post(f"{base}/{sid}/debrief").json()
    assert s["debrief"] is not None and 1 <= s["debrief"]["score"] <= 10
    assert [x["id"] for x in client.get(base).json()] == [sid]
