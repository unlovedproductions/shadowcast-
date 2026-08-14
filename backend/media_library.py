"""Operator media library inventory — find/reuse music beds and B-roll.

Addresses research counter (source 29): scarcity is often findability.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from audio_options import MOOD_SETTINGS_KEYS
from broll import broll_dir

EXPECTED_MUSIC_MOODS: tuple[str, ...] = tuple(MOOD_SETTINGS_KEYS)
EXPECTED_BROLL_TAGS: tuple[str, ...] = (
    "pad",
    "default",
    "pros",
    "cons",
    "verdict",
    "comparison",
)

_MUSIC_EXTS = (".wav", ".mp3", ".flac")
_BROLL_EXTS = (".mp4", ".mov", ".webm", ".mkv")


def music_dir() -> Path:
    return Path(__file__).resolve().parent / "assets" / "music"


def _rel_asset(path: Path) -> str:
    try:
        backend = Path(__file__).resolve().parent
        return str(path.resolve().relative_to(backend))
    except ValueError:
        return str(path)


def _file_bytes(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def inventory_music() -> list[dict[str, Any]]:
    """List expected moods + any extra beds on disk."""
    root = music_dir()
    on_disk: dict[str, Path] = {}
    if root.is_dir():
        for path in sorted(root.iterdir()):
            if not path.is_file():
                continue
            lower = path.name.lower()
            for ext in _MUSIC_EXTS:
                if lower.endswith(ext):
                    mood = path.name[: -len(ext)]
                    on_disk[mood.lower()] = path
                    break

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for mood in EXPECTED_MUSIC_MOODS:
        key = mood.lower()
        seen.add(key)
        path = on_disk.get(key)
        present = path is not None
        rows.append(
            {
                "kind": "music",
                "id": mood,
                "tags": ["music", "mood", mood],
                "path": _rel_asset(path) if path else f"assets/music/{mood}.wav",
                "bytes": _file_bytes(path) if path else 0,
                "present": present,
                "expected": True,
            }
        )
    for key, path in on_disk.items():
        if key in seen:
            continue
        rows.append(
            {
                "kind": "music",
                "id": path.stem,
                "tags": ["music", "mood", path.stem, "extra"],
                "path": _rel_asset(path),
                "bytes": _file_bytes(path),
                "present": True,
                "expected": False,
            }
        )
    return rows


def inventory_broll() -> list[dict[str, Any]]:
    """List expected section pads + any extra clips on disk."""
    root = broll_dir()
    on_disk: dict[str, Path] = {}
    if root.is_dir():
        for path in sorted(root.iterdir()):
            if path.is_file() and path.suffix.lower() in _BROLL_EXTS:
                on_disk[path.stem.lower()] = path

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tag in EXPECTED_BROLL_TAGS:
        key = tag.lower()
        seen.add(key)
        path = on_disk.get(key)
        present = path is not None
        rows.append(
            {
                "kind": "broll",
                "id": tag,
                "tags": ["broll", "section", tag],
                "path": _rel_asset(path) if path else f"assets/broll/{tag}.mp4",
                "bytes": _file_bytes(path) if path else 0,
                "present": present,
                "expected": True,
            }
        )
    for key, path in on_disk.items():
        if key in seen:
            continue
        rows.append(
            {
                "kind": "broll",
                "id": path.stem,
                "tags": ["broll", "section", path.stem, "extra"],
                "path": _rel_asset(path),
                "bytes": _file_bytes(path),
                "present": True,
                "expected": False,
            }
        )
    return rows


def _matches_query(row: dict[str, Any], q: str) -> bool:
    needle = q.strip().lower()
    if not needle:
        return True
    hay = " ".join(
        [
            str(row.get("kind") or ""),
            str(row.get("id") or ""),
            str(row.get("path") or ""),
            " ".join(str(t) for t in (row.get("tags") or [])),
        ]
    ).lower()
    return needle in hay


def media_library_snapshot(query: str | None = None) -> dict[str, Any]:
    """Full inventory with optional substring search across id/tags/path."""
    music = inventory_music()
    broll = inventory_broll()
    q = (query or "").strip()
    if q:
        music = [r for r in music if _matches_query(r, q)]
        broll = [r for r in broll if _matches_query(r, q)]

    music_present = [r["id"] for r in inventory_music() if r["present"]]
    music_missing = [
        r["id"] for r in inventory_music() if r.get("expected") and not r["present"]
    ]
    broll_present = [r["id"] for r in inventory_broll() if r["present"]]
    broll_missing = [
        r["id"] for r in inventory_broll() if r.get("expected") and not r["present"]
    ]

    return {
        "query": q or None,
        "fetch_script": "scripts/fetch_operator_media.sh",
        "music": {
            "expected_moods": list(EXPECTED_MUSIC_MOODS),
            "present": music_present,
            "missing": music_missing,
            "items": music,
        },
        "broll": {
            "expected_tags": list(EXPECTED_BROLL_TAGS),
            "present": broll_present,
            "missing": broll_missing,
            "items": broll,
        },
        "summary": {
            "music_present_count": len(music_present),
            "music_missing_count": len(music_missing),
            "broll_present_count": len(broll_present),
            "broll_missing_count": len(broll_missing),
            "complete": not music_missing and not broll_missing,
        },
    }
