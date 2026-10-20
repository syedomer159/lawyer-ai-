"""The list of cases. Holds no case content: that lives only in each case's own store (ADR-0001)."""

import json
import re
import shutil
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.contracts.cases import USER_SIDES, Case, CaseCreate

CASE_ID = re.compile(r"^[0-9a-f]{32}$")

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    client TEXT NOT NULL,
    user_side TEXT NOT NULL CHECK (user_side IN ({", ".join(f"'{s}'" for s in USER_SIDES)})),
    charges TEXT NOT NULL,
    local_only INTEGER NOT NULL,
    embed_model TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


class Registry:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(data_dir / "registry.db", check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute(_SCHEMA)

    def close(self) -> None:
        self.db.close()

    def case_dir(self, case_id: str) -> Path:
        # The id becomes a folder name: only accept our own hex ids (no "..", no slashes).
        if not CASE_ID.match(case_id):
            raise ValueError(f"invalid case id {case_id!r}")
        return self.data_dir / "cases" / case_id

    def create(self, body: CaseCreate, embed_model: str) -> Case:
        case = Case(
            id=uuid.uuid4().hex,
            embed_model=embed_model,
            created_at=datetime.now(UTC).isoformat(timespec="seconds"),
            **body.model_dump(),
        )
        with self.db:
            self.db.execute(
                "INSERT INTO cases VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (case.id, case.title, case.client, case.user_side, json.dumps(case.charges),
                 int(case.local_only), case.embed_model, case.created_at),
            )  # fmt: skip
        return case

    def list(self) -> list[Case]:
        rows = self.db.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
        return [_to_case(r) for r in rows]

    def get(self, case_id: str) -> Case | None:
        row = self.db.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return _to_case(row) if row else None

    def delete(self, case_id: str) -> None:
        folder = self.case_dir(case_id)
        with self.db:
            self.db.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        if folder.exists():
            shutil.rmtree(folder)


def _to_case(row: sqlite3.Row) -> Case:
    return Case(
        id=row["id"],
        title=row["title"],
        client=row["client"],
        user_side=row["user_side"],
        charges=json.loads(row["charges"]),
        local_only=bool(row["local_only"]),
        embed_model=row["embed_model"],
        created_at=row["created_at"],
    )
