"""Add `shared/` to sys.path so bots can `import rulc_theme`."""

from __future__ import annotations

import sys
from pathlib import Path

_SHARED: Path | None = None


def ensure_shared_path() -> Path:
    global _SHARED
    if _SHARED is not None:
        return _SHARED

    here = Path(__file__).resolve().parent
    shared = here.parent
    if shared.name != "shared" or not (shared / "rulc_theme").is_dir():
        raise RuntimeError("rulc_theme bootstrap: expected shared/rulc_theme layout")

    shared_str = str(shared)
    if shared_str not in sys.path:
        sys.path.insert(0, shared_str)

    _SHARED = shared
    return shared
