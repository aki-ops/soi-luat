from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    raw = os.environ.get("SOILUAT_DATA")
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.cwd() / "data").resolve()


def db_path() -> Path:
    return data_dir() / "soiluat.db"


HOST = "127.0.0.1"
PORT = 8000
