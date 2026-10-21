from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.store.case_store import MIGRATIONS, CaseStore


def test_concurrent_first_opens_migrate_once(tmp_path: Path) -> None:
    """The UI fires several requests at once; each opens the case store in its own thread.
    Only one may run each migration, the rest must see the result."""

    def open_store(_: int) -> int:
        store = CaseStore(tmp_path / "case")
        try:
            return store.db.execute("PRAGMA user_version").fetchone()[0]
        finally:
            store.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        versions = list(pool.map(open_store, range(8)))
    assert versions == [len(MIGRATIONS)] * 8
