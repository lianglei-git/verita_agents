"""Safe file resolution under allowed media roots."""

from __future__ import annotations

from pathlib import Path


def allowed_media_roots() -> list[Path]:
    from backend.config import MEDIA_ASR_DIR, MEDIA_ROOT, MEDIA_TTS_DIR

    roots: list[Path] = []
    for raw in (MEDIA_ROOT, MEDIA_TTS_DIR, MEDIA_ASR_DIR):
        if not raw:
            continue
        p = Path(raw).expanduser().resolve()
        if p not in roots:
            roots.append(p)
    return roots


def resolve_media_file(path: str) -> Path | None:
    """
    Resolve a user-supplied path to a readable file under media roots.
    Accepts absolute paths or paths relative to MEDIA_ROOT / TTS / ASR dirs.
    """
    raw = (path or "").strip()
    if not raw:
        return None

    candidate = Path(raw).expanduser()
    roots = allowed_media_roots()

    if candidate.is_absolute():
        target = candidate.resolve()
    else:
        target = None
        for root in roots:
            trial = (root / candidate).resolve()
            if _is_under(trial, root) and trial.is_file():
                target = trial
                break
        if target is None:
            return None

    if not target.is_file():
        return None
    if not any(_is_under(target, root) for root in roots):
        return None
    return target


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
