from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

STATE_DIR = Path("state")


def _paused_path() -> Path:
    return STATE_DIR / "paused"


def _last_run_path() -> Path:
    return STATE_DIR / "last_run.json"


def _ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def set_paused(reason: str) -> None:
    _ensure_state_dir()
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    _paused_path().write_text(f"{reason.strip()}\n{timestamp}\n", encoding="utf-8")


def clear_paused() -> bool:
    path = _paused_path()
    if not path.is_file():
        return False
    path.unlink()
    return True


def is_paused() -> bool:
    return _paused_path().is_file()


def read_paused() -> tuple[str, str] | None:
    path = _paused_path()
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return None
    reason = lines[0].strip()
    timestamp = lines[1].strip() if len(lines) > 1 else ""
    return reason, timestamp


def write_last_run(result: str) -> None:
    _ensure_state_dir()
    payload = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "result": result,
    }
    _last_run_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def read_last_run() -> dict[str, str] | None:
    path = _last_run_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    timestamp = data.get("timestamp")
    result = data.get("result")
    if not isinstance(timestamp, str) or not isinstance(result, str):
        return None
    return {"timestamp": timestamp, "result": result}
