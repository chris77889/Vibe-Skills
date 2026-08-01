from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from shutil import copy2
from typing import Any

CONTRACTS_SRC = Path(__file__).resolve().parents[3] / "contracts" / "src"
if CONTRACTS_SRC.is_dir() and str(CONTRACTS_SRC) not in sys.path:
    sys.path.insert(0, str(CONTRACTS_SRC))

from vgo_contracts.live_governance_contract import (  # noqa: E402
    LiveGovernanceContract,
    RunArtifactManifest,
    load_live_governance_contract,
)


@dataclass(frozen=True, slots=True)
class RuntimeArtifactProjection:
    """Resolved paths for the one live run-artifact contract."""

    contract: LiveGovernanceContract
    workspace_root: Path
    run_id: str
    run_root: Path
    artifact_paths: dict[str, Path]
    primary_document_paths: dict[str, Path]
    legacy_run_root: Path
    legacy_projection_enabled: bool

    @property
    def manifest_path(self) -> Path:
        return self.artifact_paths["manifest"]

    @property
    def artifact_sink(self):
        return self.contract.artifact_sink

    def relative_run_root(self) -> str:
        return (Path(self.artifact_sink.root) / self.run_id).as_posix()


def _load_contract(repo_root: Path) -> LiveGovernanceContract:
    try:
        return load_live_governance_contract(repo_root.resolve())
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        raise RuntimeError(
            f"live governance artifact contract is required: {exc}"
        ) from exc


def resolve_runtime_artifact_projection(
    *,
    agent_root: Path,
    workspace_root: Path | None,
    run_id: str,
    repo_root: Path,
) -> RuntimeArtifactProjection:
    resolved_agent_root = agent_root.resolve()
    resolved_workspace_root = (
        workspace_root.resolve() if workspace_root is not None else resolved_agent_root
    )
    normalized_run_id = str(run_id).strip()
    contract = _load_contract(repo_root.resolve())
    sink = contract.artifact_sink
    normalized_workspace = resolved_workspace_root.as_posix().rstrip("/").casefold()
    if any(
        normalized_workspace.endswith("/" + legacy_root.casefold().rstrip("/"))
        for legacy_root in sink.legacy_documentation_roots
    ):
        raise ValueError(
            "historical documentation roots cannot be used as the artifact workspace"
        )
    run_root = sink.resolve_run_root(resolved_workspace_root, normalized_run_id)
    artifact_paths = sink.resolve_run_artifact_paths(
        resolved_workspace_root,
        normalized_run_id,
    )
    primary_document_paths = sink.resolve_run_primary_document_paths(
        resolved_workspace_root,
        normalized_run_id,
    )
    return RuntimeArtifactProjection(
        contract=contract,
        workspace_root=resolved_workspace_root,
        run_id=normalized_run_id,
        run_root=run_root,
        artifact_paths=artifact_paths,
        primary_document_paths=primary_document_paths,
        legacy_run_root=(
            resolved_agent_root / "vibe" / "runs" / normalized_run_id
        ).resolve(),
        # Calls that omit workspace_root are the pre-contract Python API. Keep
        # a marked read-compatible projection until that API is removed.
        legacy_projection_enabled=workspace_root is None,
    )


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _write_primary_document(
    path: Path,
    *,
    kind: str,
    run_id: str,
    schema_version: int,
    payload: dict[str, Any],
) -> Path:
    payload_text = json.dumps(payload, ensure_ascii=False, indent=2)
    fence = "```"
    while fence in payload_text:
        fence += "`"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            (
                f"# Run {kind.title()}",
                "",
                f"- Run ID: `{run_id}`",
                f"- Schema version: `{schema_version}`",
                "",
                "## Payload",
                "",
                f"{fence}json",
                payload_text,
                fence,
                "",
            )
        ),
        encoding="utf-8",
    )
    return path


def _git_commit_sha(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return str(os.environ.get("VGO_COMMIT_SHA") or "unknown").strip() or "unknown"
    return completed.stdout.strip() or "unknown"


def execution_environment(*, repo_root: Path, host_id: str | None = None) -> dict[str, str]:
    del repo_root
    return {
        "os": platform.system().lower() or "unknown",
        "runtime": "python",
        "runtime_version": platform.python_version(),
        "host_id": str(host_id or "unknown").strip() or "unknown",
    }


def _envelope(*, kind: str, run_id: str, payload: dict[str, Any], schema_version: int) -> dict[str, Any]:
    return {
        **payload,
        "schema_version": schema_version,
        "artifact_kind": kind,
        "run_id": run_id,
        "payload": payload,
    }


def write_runtime_artifact_bundle(
    projection: RuntimeArtifactProjection,
    *,
    requirement: dict[str, Any],
    plan: dict[str, Any],
    status: dict[str, Any],
    proof: dict[str, Any],
    repo_root: Path,
    host_id: str | None = None,
    legacy_writes: list[str] | None = None,
) -> RunArtifactManifest:
    """Write the required artifacts and validate the manifest before returning."""
    sink = projection.artifact_sink
    payloads = {
        "requirement": requirement,
        "plan": plan,
        "status": status,
        "proof": proof,
    }
    for kind in sink.required_artifacts:
        path = projection.artifact_paths[kind]
        _write_json(
            path,
            _envelope(
                kind=kind,
                run_id=projection.run_id,
                payload=payloads[kind],
                schema_version=sink.schema_version,
            ),
        )
    for kind, path in projection.primary_document_paths.items():
        _write_primary_document(
            path,
            kind=kind,
            run_id=projection.run_id,
            schema_version=sink.schema_version,
            payload=payloads[kind],
        )

    resolved_legacy_writes = list(legacy_writes or [])
    if sink.legacy_write_mode == "disabled" and resolved_legacy_writes:
        raise ValueError("disabled legacy compatibility cannot declare writes")
    compatibility = {
        "mode": sink.legacy_write_mode,
        "removal_release": sink.legacy_removal_release,
        "documentation_roots": list(sink.legacy_documentation_roots),
        "writes": resolved_legacy_writes,
        "observable": True,
    }
    manifest_payload = {
        "schema_version": sink.schema_version,
        "run_id": projection.run_id,
        "artifact_root": projection.relative_run_root(),
        "artifacts": {
            kind: sink.artifact_path_map[kind] for kind in sink.required_artifacts
        },
        "commit_sha": _git_commit_sha(repo_root.resolve()),
        "execution_environment": execution_environment(
            repo_root=repo_root,
            host_id=host_id,
        ),
        "legacy_compatibility": compatibility,
    }
    manifest = projection.contract.validate_run_artifact_manifest(manifest_payload)
    _write_json(projection.manifest_path, manifest.model_dump())
    _write_json(
        projection.artifact_paths["legacy_compatibility"],
        {
            "run_id": projection.run_id,
            "artifact_root": projection.relative_run_root(),
            **compatibility,
        },
    )
    if projection.legacy_projection_enabled:
        _mirror_legacy_projection(projection)
    return manifest


def _copy_run_tree(*, source_root: Path, destination_root: Path) -> None:
    destination_root.mkdir(parents=True, exist_ok=True)
    for source in source_root.rglob("*"):
        if not source.is_file():
            continue
        destination = destination_root / source.relative_to(source_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(source, destination)


def _mirror_legacy_projection(projection: RuntimeArtifactProjection) -> None:
    if projection.legacy_run_root == projection.run_root:
        return
    _copy_run_tree(
        source_root=projection.run_root,
        destination_root=projection.legacy_run_root,
    )


def seed_canonical_run_from_legacy_if_needed(
    projection: RuntimeArtifactProjection,
) -> bool:
    """Copy a pre-contract run into the canonical sink before resuming it."""
    if (
        not projection.legacy_projection_enabled
        or projection.run_root.exists()
        or not projection.legacy_run_root.is_dir()
    ):
        return False
    _copy_run_tree(
        source_root=projection.legacy_run_root,
        destination_root=projection.run_root,
    )
    return True


def mirror_legacy_run_if_needed(projection: RuntimeArtifactProjection) -> None:
    """Refresh the compatibility tree after later work-unit writes."""
    if projection.legacy_projection_enabled:
        _mirror_legacy_projection(projection)


def load_runtime_artifact_manifest(
    projection: RuntimeArtifactProjection,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    path = path or projection.manifest_path
    if not path.is_file():
        raise ValueError(f"missing run artifact manifest: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"run artifact manifest must be an object: {path}")
    projection.contract.validate_run_artifact_manifest(payload)
    return payload


__all__ = [
    "RuntimeArtifactProjection",
    "execution_environment",
    "load_runtime_artifact_manifest",
    "mirror_legacy_run_if_needed",
    "resolve_runtime_artifact_projection",
    "seed_canonical_run_from_legacy_if_needed",
    "write_runtime_artifact_bundle",
]
