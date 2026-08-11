from __future__ import annotations

from pathlib import Path
import shutil


def seed_live_document_contract(
    workspace_root: Path,
    *,
    source_root: Path | None = None,
) -> None:
    """Seed the executable live contract into a temporary workspace fixture."""
    repository_root = source_root or Path(__file__).resolve().parents[2]
    config_root = workspace_root / "config"
    config_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        repository_root / "config" / "live-document-contract.json",
        config_root / "live-document-contract.json",
    )
