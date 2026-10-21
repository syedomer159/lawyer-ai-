from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents.analysis import dedupe_conflicts, merge_parties
from app.agents.arguments import select_issues
from app.agents.assessment import legal_checklist
from app.agents.extractor import ExtractedParty, Extraction
from app.citations import CheckedCitation, Citation, CitationChecker, quote_score
from app.contracts.analysis import CrossQuestion
from app.ingest.pipeline import ingest_document
from app.store.analysis_store import (
    AdverseRow,
    AnalysisResult,
    ClaimRow,
    ConflictRow,
    ElementRow,
    IssueRow,
    load_analysis,
    save_analysis,
    set_conflict_status,
    start_job,
)
from app.store.case_store import CaseStore
from tests.conftest import CASE1, FakeEmbedder, create_case, upload

# --- citations ------------------------------------------------------------------------------


def test_quote_score_exact_fuzzy_and_wrong() -> None:
    text = "The street light was on and I saw his face clearly.\nHe was thin."
    assert quote_score("street light was ON and  I saw", text) == 1.0  # case/space-insensitive
    assert quote_score("The streat light was on and I saw his face", text) >= 0.9  # OCR typo
    assert quote_score("the street light was not working", text) < 0.9


@pytest.fixture
def store(tmp_path: Path) -> CaseStore:
    return CaseStore(tmp_path / "case")


async def _ingest(store: CaseStore, *paths: Path) -> None:
    for path in paths:
        kind = "pdf" if path.suffix == ".pdf" else "text"
        doc = store.add_document(path.name, kind, sha256=path.name)
        store.file_path(doc).write_bytes(path.read_bytes())
        await ingest_document(store, doc, FakeEmbedder())


@pytest.mark.anyio
async def test_checker_only_accepts_quotes_from_the_cited_chunk(store: CaseStore) -> None:
    await _ingest(store, CASE1 / "03_Statement_Ramesh_Kumar_PW2.pdf", CASE1 / "10_MLC_Report.pdf")
    checker = CitationChecker(store)
    texts = store.chunk_texts()
    ramesh = next(cid for cid, t in texts.items() if "red jacket" in t)
    mlc = next(cid for cid, t in texts.items() if "No external injury" in t)

    assert checker.check(Citation(chunk_id=ramesh, quote="a man in a red jacket")).verified
    assert not checker.check(Citation(chunk_id=mlc, quote="a man in a red jacket")).verified
    assert checker.problems([Citation(chunk_id=999_999, quote="x")]) == [
        "chunk 999999 does not exist"
    ]
    store.close()


# --- workflow helpers -----------------------------------------------------------------------


def test_parties_merge_across_titles_and_roles() -> None:
    a = Extraction(parties=[ExtractedParty(name="Smt. Sunita Sharma", role="other")], claims=[])
    b = Extraction(
        parties=[
            ExtractedParty(name="Sunita Sharma", role="complainant"),
            ExtractedParty(name="SI Pradeep Rathore", role="io"),
        ],
        claims=[],
    )
    merged = dict((name.split()[-1], role) for name, role in merge_parties([a, b]))
    assert merged == {"Sharma": "complainant", "Rathore": "io"}


def test_legal_checklist_uses_curated_elements_and_flags_unverified() -> None:
    text, unverified = legal_checklist(["BNS 304(2)"])
    assert "suddenly, quickly or forcibly seized" in text and "BNSS 105" in text
    assert unverified  # the procedure list has unverified section numbers
    text, _ = legal_checklist(["IPC 999"])
    assert "IPC 999: no curated elements" in text


def _cite(chunk_id: int = 1) -> CheckedCitation:
    return CheckedCitation(chunk_id, "q", True)


def _claim(key: int, chunk_id: int = 1) -> ClaimRow:
    return ClaimRow(key, "W", "time", f"claim {key}", None, _cite(chunk_id))


def test_issue_selection_order_and_filters() -> None:
    claims = [_claim(0), _claim(1, 2)]
    conflicts = [
        ConflictRow("lighting", "testimony_vs_document", "medium", "helps", "m", [0, 1]),
        ConflictRow("time", "testimony_vs_testimony", "high", "helps", "h", [0, 1]),
        ConflictRow("minor", "testimony_vs_testimony", "low", "helps", "l", [0, 1]),
        ConflictRow("against us", "testimony_vs_testimony", "high", "hurts", "x", [0, 1]),
    ]
    elements = [
        ElementRow("procedure", "TIP held", "missing", "none", [_cite(2)]),
        ElementRow("offence", "theft", "supported", "ok", [_cite(1)]),
    ]
    issues = select_issues(conflicts, elements, [AdverseRow("PW2 identifies", [_cite(1)])], claims)
    titles = [i.description.split(":")[0] for i in issues]
    assert titles == [
        "Contradiction about time",
        "Contradiction about lighting",
        "The procedure point 'TIP held' is missing",
        "Evidence against our client",
    ]
    assert [c.key for c in issues[2].evidence] == [1]  # evidence = claims from the cited chunk


@pytest.mark.anyio
async def test_save_and_load_roundtrip(store: CaseStore) -> None:
    await _ingest(store, CASE1 / "01_FIR_112-2026.pdf", CASE1 / "03_Statement_Ramesh_Kumar_PW2.pdf")
    texts = store.chunk_texts()
    fir = next(cid for cid, t in texts.items() if "21:15 hrs" in t)
    pw2 = next(cid for cid, t in texts.items() if "8:30 pm" in t)
    c0 = ClaimRow(
        0,
        "Sunita Sharma",
        "time",
        "At 21:15",
        "2026-03-12T21:15",
        CheckedCitation(fir, "at about 21:15 hrs", True),
    )
    c1 = ClaimRow(
        1,
        "Ramesh Kumar",
        "time",
        "At 8:30 pm",
        "2026-03-12T20:30",
        CheckedCitation(pw2, "at about 8:30 pm", True),
    )
    result = AnalysisResult(
        parties=[("Ramesh Kumar", "witness")],
        claims=[c0, c1],
        conflicts=[
            ConflictRow("time", "testimony_vs_testimony", "high", "helps", "45 min", [0, 1])
        ],
        elements=[ElementRow("procedure", "Prompt FIR", "weak", "delay", [c0.citation])],
        adverse=[],
        issues=[
            IssueRow(
                "Time",
                "a",
                "b",
                "c",
                [CrossQuestion(witness="Ramesh", question="q?")],
                [c1.citation],
            )
        ],
    )
    save_analysis(store, result)
    loaded = load_analysis(store)

    (conflict,) = loaded.conflicts
    assert [c.citation.ref.filename for c in conflict.claims] == [
        "01_FIR_112-2026.pdf",
        "03_Statement_Ramesh_Kumar_PW2.pdf",
    ]
    assert [c.when for c in loaded.timeline] == ["2026-03-12T20:30", "2026-03-12T21:15"]
    assert loaded.elements[0].citations[0].ref.page == 1
    assert loaded.issues[0].cross_questions[0].question == "q?"

    assert set_conflict_status(store, conflict.id, "dismissed")
    assert load_analysis(store).conflicts[0].status == "dismissed"
    save_analysis(store, AnalysisResult())  # a new run replaces everything
    assert load_analysis(store).conflicts == []
    store.close()


# --- API (offline TestModel for every role) -------------------------------------------------


def test_analysis_api_runs_workflow_offline(client: TestClient) -> None:
    case_id = create_case(client)
    assert client.post(f"/api/cases/{case_id}/analysis").status_code == 400  # no documents yet

    upload(
        client, case_id, CASE1 / "03_Statement_Ramesh_Kumar_PW2.pdf", CASE1 / "10_MLC_Report.pdf"
    )
    res = client.post(f"/api/cases/{case_id}/analysis")
    assert res.status_code == 202

    analysis = client.get(f"/api/cases/{case_id}/analysis").json()
    assert analysis["job"]["status"] == "done", analysis["job"]
    usage = client.get(f"/api/cases/{case_id}/usage").json()
    assert {r["role"] for r in usage["by_role"]} >= {"extractor", "analyst"}
    # TestModel cites chunks that don't exist: nothing unverified may surface as a claim.
    assert all(c["citation"]["verified"] for f in analysis["conflicts"] for c in f["claims"])


def test_second_analysis_is_rejected_while_one_runs(client: TestClient, tmp_path: Path) -> None:
    case_id = create_case(client)
    upload(client, case_id, CASE1 / "11_Client_Interview_Notes.txt")
    store = CaseStore(tmp_path / "cases" / case_id)
    start_job(store, "analysis")
    store.close()
    assert client.post(f"/api/cases/{case_id}/analysis").status_code == 409


def test_conflicts_found_in_two_aspects_are_merged_keeping_most_severe() -> None:
    a = ConflictRow("speed", "testimony_vs_physical", "medium", "helps", "a", [1, 2])
    b = ConflictRow("impact", "testimony_vs_physical", "high", "helps", "b", [2, 1])
    c = ConflictRow("colour", "testimony_vs_document", "low", "helps", "c", [1, 3])
    assert [x.explanation for x in dedupe_conflicts([a, b, c])] == ["b", "c"]
