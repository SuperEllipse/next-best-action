"""Patch sqlite3 for CrewAI/Chroma on platforms with an older system sqlite."""

import sys


def ensure_sqlite3() -> None:
    """Use pysqlite3 when available; otherwise require system sqlite >= 3.35."""
    try:
        import pysqlite3.dbapi2 as _sqlite3  # type: ignore[import-not-found]

        sys.modules["sqlite3"] = _sqlite3
        return
    except ImportError:
        pass

    import sqlite3

    if sqlite3.sqlite_version_info < (3, 35, 0):
        raise RuntimeError(
            "sqlite3 >= 3.35.0 is required for CrewAI (Chroma). "
            "Install project dependencies: pip install -r requirements.txt "
            "(includes pysqlite3-binary), then restart the Application."
        )


ensure_sqlite3()
