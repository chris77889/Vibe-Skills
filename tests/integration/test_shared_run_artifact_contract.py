from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_SRC = REPO_ROOT / "packages" / "contracts" / "src"
RUNTIME_SRC = REPO_ROOT / "packages" / "runtime-core" / "src"
RUNTIME_INVOCATION_TIMEOUT_SECONDS = 120
for source_root in (CONTRACTS_SRC, RUNTIME_SRC):
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))

from vgo_runtime.artifact_contract import (  # noqa: E402
    resolve_runtime_artifact_projection,
    write_runtime_artifact_bundle,
)
from vgo_contracts.live_governance_contract import (  # noqa: E402
    LiveGovernanceContract,
)


def _powershell() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell executable not available")
    return executable


def _ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_powershell_json(script: str) -> dict[str, object]:
    completed = subprocess.run(
        [
            _powershell(),
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        timeout=RUNTIME_INVOCATION_TIMEOUT_SECONDS,
    )
    payload = json.loads(completed.stdout)
    assert isinstance(payload, dict)
    return payload


def _dot_source_common() -> str:
    common = REPO_ROOT / "scripts" / "runtime" / "VibeRuntime.Common.ps1"
    return f"$ErrorActionPreference = 'Stop'; . {_ps_quote(common)}; "


def test_python_and_powershell_resolve_the_same_run_artifact_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_id = "artifact-path-parity"
    python_projection = resolve_runtime_artifact_projection(
        agent_root=workspace,
        workspace_root=workspace,
        run_id=run_id,
        repo_root=REPO_ROOT,
    )
    powershell_projection = _run_powershell_json(
        _dot_source_common()
        + "$result = Get-VibeArtifactContractDescriptor "
        + f"-RepoRoot {_ps_quote(REPO_ROOT)} -RunId {_ps_quote(run_id)} "
        + f"-ArtifactRoot {_ps_quote(workspace)}; "
        + "$result | ConvertTo-Json -Depth 20"
    )

    expected_root = workspace / ".vibeskills" / "runs" / run_id
    assert python_projection.run_root == expected_root.resolve()
    assert Path(str(powershell_projection["artifact_root"])) == expected_root.resolve()
    for kind in (
        "requirement",
        "plan",
        "status",
        "proof",
        "manifest",
        "legacy_compatibility",
    ):
        assert Path(str(powershell_projection["paths"][kind])) == python_projection.artifact_paths[kind]
    for kind in ("requirement", "plan"):
        assert Path(
            str(powershell_projection["paths"][f"primary_{kind}"])
        ) == python_projection.primary_document_paths[kind]


def test_python_and_powershell_normalize_run_ids_once(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    raw_run_id = "  normalized-run-id  "
    python_projection = resolve_runtime_artifact_projection(
        agent_root=workspace,
        workspace_root=workspace,
        run_id=raw_run_id,
        repo_root=REPO_ROOT,
    )
    powershell_projection = _run_powershell_json(
        _dot_source_common()
        + "$result = Get-VibeArtifactContractDescriptor "
        + f"-RepoRoot {_ps_quote(REPO_ROOT)} -RunId {_ps_quote(raw_run_id)} "
        + f"-ArtifactRoot {_ps_quote(workspace)}; "
        + "$result | ConvertTo-Json -Depth 20"
    )

    expected_root = (workspace / ".vibeskills" / "runs" / "normalized-run-id").resolve()
    assert python_projection.run_id == "normalized-run-id"
    assert python_projection.run_root == expected_root
    assert python_projection.legacy_run_root == (
        workspace / "vibe" / "runs" / "normalized-run-id"
    ).resolve()
    assert powershell_projection["run_id"] == "normalized-run-id"
    assert Path(str(powershell_projection["artifact_root"])) == expected_root
    assert powershell_projection["artifact_root_relative"] == (
        ".vibeskills/runs/normalized-run-id"
    )


def test_python_and_powershell_follow_custom_contract_paths(tmp_path: Path) -> None:
    contract_repo = tmp_path / "contract-repo"
    workspace = tmp_path / "workspace"
    (contract_repo / "config").mkdir(parents=True)
    workspace.mkdir()
    payload = json.loads(
        (REPO_ROOT / "config" / "live-document-contract.json").read_text(
            encoding="utf-8"
        )
    )
    payload["artifact_sink"]["artifact_paths"] = {
        "requirement": "records/requirement.json",
        "plan": "records/plan.json",
        "status": "records/status.json",
        "proof": "records/proof.json",
    }
    payload["artifact_sink"]["primary_document_paths"] = {
        "requirement": "documents/requirement.md",
        "plan": "documents/plan.md",
    }
    payload["artifact_sink"]["manifest_path"] = "metadata/manifest.json"
    payload["artifact_sink"]["legacy_compatibility_path"] = (
        "metadata/legacy-compatibility.json"
    )
    (contract_repo / "config" / "live-document-contract.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    run_id = "custom-contract-paths"

    python_projection = resolve_runtime_artifact_projection(
        agent_root=workspace,
        workspace_root=workspace,
        run_id=run_id,
        repo_root=contract_repo,
    )
    powershell_projection = _run_powershell_json(
        _dot_source_common()
        + "$result = Get-VibeArtifactContractDescriptor "
        + f"-RepoRoot {_ps_quote(contract_repo)} -RunId {_ps_quote(run_id)} "
        + f"-ArtifactRoot {_ps_quote(workspace)}; "
        + "$result | ConvertTo-Json -Depth 20"
    )

    for kind in (
        "requirement",
        "plan",
        "status",
        "proof",
        "manifest",
        "legacy_compatibility",
    ):
        assert Path(str(powershell_projection["paths"][kind])) == (
            python_projection.artifact_paths[kind]
        )
    for kind in ("requirement", "plan"):
        assert Path(
            str(powershell_projection["paths"][f"primary_{kind}"])
        ) == python_projection.primary_document_paths[kind]


def test_repository_contract_overrides_a_conflicting_workspace_copy(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    config_root = workspace / "config"
    config_root.mkdir(parents=True)
    payload = json.loads(
        (REPO_ROOT / "config" / "live-document-contract.json").read_text(
            encoding="utf-8"
        )
    )
    payload["artifact_sink"]["root"] = ".workspace-contract/runs"
    (config_root / "live-document-contract.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    projection = resolve_runtime_artifact_projection(
        agent_root=workspace,
        workspace_root=workspace,
        run_id="repo-contract-authority",
        repo_root=REPO_ROOT,
    )
    powershell_projection = _run_powershell_json(
        _dot_source_common()
        + "$result = Get-VibeArtifactContractDescriptor "
        + f"-RepoRoot {_ps_quote(REPO_ROOT)} -RunId 'repo-contract-authority' "
        + f"-WorkspaceRoot {_ps_quote(workspace)}; "
        + "$result | ConvertTo-Json -Depth 20"
    )

    expected_root = (
        workspace / ".vibeskills" / "runs" / "repo-contract-authority"
    ).resolve()
    assert projection.run_root == expected_root
    assert Path(str(powershell_projection["artifact_root"])) == expected_root


def test_python_and_powershell_emit_manifest_and_artifact_envelope_parity(tmp_path: Path) -> None:
    run_id = "artifact-payload-parity"
    python_workspace = tmp_path / "python"
    powershell_workspace = tmp_path / "powershell"
    python_workspace.mkdir()
    powershell_workspace.mkdir()
    payloads = {
        "requirement": {"task": "verify artifact parity"},
        "plan": {"status": "ready"},
        "status": {"status": "ready_for_execution"},
        "proof": {"status": "pending"},
    }
    projection = resolve_runtime_artifact_projection(
        agent_root=python_workspace,
        workspace_root=python_workspace,
        run_id=run_id,
        repo_root=REPO_ROOT,
    )
    python_manifest = write_runtime_artifact_bundle(
        projection,
        repo_root=REPO_ROOT,
        host_id="codex",
        **payloads,
    ).model_dump()
    powershell_result = _run_powershell_json(
        _dot_source_common()
        + "Remove-Item Env:OS -ErrorAction SilentlyContinue; "
        + "$result = Write-VibeRunArtifactBundle "
        + f"-RepoRoot {_ps_quote(REPO_ROOT)} -RunId {_ps_quote(run_id)} "
        + f"-ArtifactRoot {_ps_quote(powershell_workspace)} -HostId 'codex' "
        + "-Requirement ([pscustomobject]@{ task = 'verify artifact parity' }) "
        + "-Plan ([pscustomobject]@{ status = 'ready' }) "
        + "-Status ([pscustomobject]@{ status = 'ready_for_execution' }) "
        + "-Proof ([pscustomobject]@{ status = 'pending' }); "
        + "$result | ConvertTo-Json -Depth 20"
    )
    powershell_manifest = powershell_result["manifest"]

    for field in ("schema_version", "run_id", "artifact_root", "artifacts", "commit_sha"):
        assert powershell_manifest[field] == python_manifest[field]
    assert powershell_manifest["execution_environment"]["os"] == python_manifest[
        "execution_environment"
    ]["os"]
    assert powershell_manifest["execution_environment"]["host_id"] == "codex"
    assert python_manifest["execution_environment"]["host_id"] == "codex"
    assert powershell_manifest["execution_environment"]["runtime"] == "powershell"
    assert python_manifest["execution_environment"]["runtime"] == "python"
    assert powershell_manifest["execution_environment"]["runtime_version"]
    assert python_manifest["execution_environment"]["runtime_version"]
    assert powershell_manifest["legacy_compatibility"] == python_manifest["legacy_compatibility"]
    assert powershell_manifest["artifacts"] == projection.artifact_sink.artifact_path_map

    for kind in ("requirement", "plan"):
        primary_document = projection.primary_document_paths[kind]
        assert primary_document.is_file()
        primary_text = primary_document.read_text(encoding="utf-8")
        assert primary_text.startswith(f"# Run {kind.title()}\n")
        assert json.dumps(payloads[kind], ensure_ascii=False, indent=2) in primary_text

    for kind in ("requirement", "plan", "status", "proof"):
        python_payload = json.loads(projection.artifact_paths[kind].read_text(encoding="utf-8"))
        powershell_path = Path(str(powershell_result["descriptor"]["paths"][kind]))
        powershell_payload = json.loads(powershell_path.read_text(encoding="utf-8"))
        assert powershell_payload == python_payload

    python_compatibility = json.loads(
        (projection.run_root / "legacy-compatibility.json").read_text(
            encoding="utf-8"
        )
    )
    powershell_compatibility = json.loads(
        Path(
            str(powershell_result["descriptor"]["paths"]["legacy_compatibility"])
        ).read_text(encoding="utf-8")
    )
    assert powershell_compatibility == python_compatibility


def test_historical_documentation_roots_are_rejected_as_artifact_workspaces(tmp_path: Path) -> None:
    legacy_root = tmp_path / "docs" / "requirements"
    legacy_root.mkdir(parents=True)

    with pytest.raises(ValueError, match="historical documentation roots"):
        resolve_runtime_artifact_projection(
            agent_root=tmp_path,
            workspace_root=legacy_root,
            run_id="reject-legacy-root",
            repo_root=REPO_ROOT,
        )

    completed = subprocess.run(
        [
            _powershell(),
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _dot_source_common()
            + "Get-VibeRunArtifactRoot "
            + f"-RepoRoot {_ps_quote(REPO_ROOT)} -RunId 'reject-legacy-root' "
            + f"-ArtifactRoot {_ps_quote(legacy_root)}",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=RUNTIME_INVOCATION_TIMEOUT_SECONDS,
    )
    assert completed.returncode != 0
    assert "historical documentation roots" in completed.stderr


def test_powershell_primary_documents_use_the_run_sink_and_report_dual_writes(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    run_id = "artifact-document-cutover"
    host_decision = {
        "agent_skill_organization": {
            "schema_version": "agent_skill_organization_v1",
            "derived_by": "agent",
            "workflow_level": "L",
            "modules": [
                {
                    "module_id": "direct_module",
                    "goal": "Produce the approved run artifacts.",
                    "candidate_skill_ids": [],
                    "required": True,
                    "depends_on": [],
                    "execution_mode": "agent_direct",
                    "write_scope": "outputs/direct/**",
                    "expected_outputs": ["outputs/direct/result.md"],
                    "verification": ["Check the frozen artifact contract."],
                    "acceptance_criteria": [
                        {
                            "criterion_id": "artifact-contract",
                            "description": "The run artifact contract is complete.",
                            "verification_mode": "automated",
                        }
                    ],
                }
            ],
            "selected_skills": [],
            "uncovered_modules": [],
            "workflow_level_contract": {
                "L": "Run the approved module serially.",
                "XL": "Use bounded waves for independent modules.",
            },
        }
    }
    env = os.environ.copy()
    env.update(
        {
            "VCO_HOST_ID": "codex",
            "VIBE_DISABLE_SERENA_BACKEND": "1",
            "VIBE_DISABLE_RUFLO_BACKEND": "1",
            "VIBE_DISABLE_COGNEE_BACKEND": "1",
            "VIBE_MEMORY_BACKEND_ROOT": str(tmp_path / "memory-backends"),
        }
    )
    subprocess.run(
        [
            _powershell(),
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / "scripts" / "runtime" / "invoke-vibe-runtime.ps1"),
            "-Task",
            "Verify the shared run artifact document cutover.",
            "-Mode",
            "interactive_governed",
            "-RunId",
            run_id,
            "-WorkspaceRoot",
            str(workspace),
            "-RequestedStageStop",
            "xl_plan",
            "-HostDecisionJson",
            json.dumps(host_decision, separators=(",", ":")),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        check=True,
        timeout=RUNTIME_INVOCATION_TIMEOUT_SECONDS,
    )

    run_root = workspace / ".vibeskills" / "runs" / run_id
    session_root = (
        workspace
        / ".vibeskills"
        / "outputs"
        / "runtime"
        / "vibe-sessions"
        / run_id
    )
    summary = json.loads(
        (session_root / "runtime-summary.json").read_text(encoding="utf-8")
    )
    requirement_receipt = json.loads(
        (session_root / "requirement-doc-receipt.json").read_text(encoding="utf-8")
    )
    plan_receipt = json.loads(
        (session_root / "execution-plan-receipt.json").read_text(encoding="utf-8")
    )
    primary_requirement = run_root / "requirement.md"
    primary_plan = run_root / "plan.md"
    legacy_requirement = Path(summary["artifacts"]["legacy_requirement_doc"])
    legacy_plan = Path(summary["artifacts"]["legacy_execution_plan"])

    assert Path(summary["artifacts"]["requirement_doc"]) == primary_requirement
    assert Path(summary["artifacts"]["execution_plan"]) == primary_plan
    assert primary_requirement.read_bytes() == legacy_requirement.read_bytes()
    assert primary_plan.read_bytes() == legacy_plan.read_bytes()
    assert legacy_requirement.is_relative_to(workspace / "docs" / "requirements")
    assert legacy_plan.is_relative_to(workspace / "docs" / "plans")
    assert Path(requirement_receipt["requirement_doc_path"]) == primary_requirement
    assert Path(requirement_receipt["legacy_requirement_doc_path"]) == legacy_requirement
    assert Path(plan_receipt["requirement_doc_path"]) == primary_requirement
    assert Path(plan_receipt["execution_plan_path"]) == primary_plan
    assert Path(plan_receipt["legacy_execution_plan_path"]) == legacy_plan

    manifest = json.loads((run_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["legacy_compatibility"] == {
        "mode": "dual_write",
        "removal_release": "4.1.0",
        "documentation_roots": ["docs/requirements", "docs/plans"],
        "writes": [str(legacy_requirement), str(legacy_plan)],
        "observable": True,
    }
    requirement_artifact = json.loads(
        (run_root / "requirement.json").read_text(encoding="utf-8")
    )
    plan_artifact = json.loads((run_root / "plan.json").read_text(encoding="utf-8"))
    assert requirement_artifact["requirement_doc_path"] == str(primary_requirement)
    assert plan_artifact["execution_plan_path"] == str(primary_plan)

    shutil.rmtree(workspace / "docs")
    assert primary_requirement.is_file()
    assert primary_plan.is_file()
    module_work_plan = json.loads(
        (run_root / "module-work-plan.json").read_text(encoding="utf-8")
    )
    assert module_work_plan["requirement_digest"] == hashlib.sha256(
        primary_requirement.read_bytes()
    ).hexdigest()


def test_invalid_run_id_is_rejected_before_the_session_directory_is_created(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "artifacts"
    result = _run_powershell_json(
        _dot_source_common()
        + f"$artifactRoot = {_ps_quote(artifact_root)}; "
        + "$runId = '../escape'; "
        + "$unsafePath = [System.IO.Path]::GetFullPath((Join-Path $artifactRoot "
        + "('outputs\\runtime\\vibe-sessions\\{0}' -f $runId))); "
        + "$errorMessage = ''; "
        + "try { Ensure-VibeSessionRoot "
        + f"-RepoRoot {_ps_quote(REPO_ROOT)} -RunId $runId "
        + "-ArtifactRoot $artifactRoot | Out-Null } "
        + "catch { $errorMessage = $_.Exception.Message }; "
        + "[pscustomobject]@{ "
        + "error = $errorMessage; "
        + "unsafe_path_exists = (Test-Path -LiteralPath $unsafePath) "
        + "} | ConvertTo-Json"
    )

    assert result["error"] == "run id must be a safe path segment."
    assert result["unsafe_path_exists"] is False


def test_session_artifact_sync_rejects_overlapping_roots(tmp_path: Path) -> None:
    session_root = tmp_path / "session"
    run_root = session_root / "nested-run"
    result = _run_powershell_json(
        _dot_source_common()
        + f"$sessionRoot = {_ps_quote(session_root)}; "
        + f"$runRoot = {_ps_quote(run_root)}; "
        + "New-Item -ItemType Directory -Path $sessionRoot -Force | Out-Null; "
        + "Set-Content -LiteralPath (Join-Path $sessionRoot 'source.txt') "
        + "-Value 'source'; "
        + "$descriptor = [pscustomobject]@{ paths = [pscustomobject]@{} }; "
        + "Sync-VibeSessionArtifactsToRunRoot "
        + "-SessionRoot $sessionRoot -RunArtifactRoot $runRoot "
        + "-ArtifactDescriptor $descriptor; "
        + "[pscustomobject]@{ destination_exists = "
        + "(Test-Path -LiteralPath (Join-Path $runRoot 'source.txt')) } "
        + "| ConvertTo-Json"
    )

    assert result["destination_exists"] is False


@pytest.mark.parametrize(
    "field",
    [
        "artifact_paths",
        "primary_document_paths",
        "manifest_path",
        "legacy_compatibility_path",
        "legacy_documentation_roots",
        "legacy_removal_release",
        "legacy_write_mode",
    ],
)
def test_python_and_powershell_reject_incomplete_artifact_contracts(
    tmp_path: Path,
    field: str,
) -> None:
    payload = json.loads(
        (REPO_ROOT / "config" / "live-document-contract.json").read_text(
            encoding="utf-8"
        )
    )
    payload["artifact_sink"].pop(field)
    malformed_repo = tmp_path / field
    config_root = malformed_repo / "config"
    config_root.mkdir(parents=True)
    (config_root / "live-document-contract.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=field):
        LiveGovernanceContract.model_validate(payload)

    completed = subprocess.run(
        [
            _powershell(),
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _dot_source_common()
            + "Get-VibeLiveGovernanceContract "
            + f"-RepoRoot {_ps_quote(malformed_repo)}",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
        check=False,
        timeout=RUNTIME_INVOCATION_TIMEOUT_SECONDS,
    )
    assert completed.returncode != 0
    assert field in completed.stderr


@pytest.mark.parametrize(
    "required_metadata",
    [
        ["commit_sha", "execution_environment", "commit_sha"],
        ["commit_sha", "execution_environment", ""],
    ],
)
def test_python_and_powershell_reject_invalid_required_metadata(
    tmp_path: Path,
    required_metadata: list[str],
) -> None:
    payload = json.loads(
        (REPO_ROOT / "config" / "live-document-contract.json").read_text(
            encoding="utf-8"
        )
    )
    payload["artifact_sink"]["required_metadata"] = required_metadata
    malformed_repo = tmp_path / "invalid-required-metadata"
    config_root = malformed_repo / "config"
    config_root.mkdir(parents=True)
    (config_root / "live-document-contract.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="required_metadata"):
        LiveGovernanceContract.model_validate(payload)

    completed = subprocess.run(
        [
            _powershell(),
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _dot_source_common()
            + "Get-VibeLiveGovernanceContract "
            + f"-RepoRoot {_ps_quote(malformed_repo)}",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
        check=False,
        timeout=RUNTIME_INVOCATION_TIMEOUT_SECONDS,
    )
    assert completed.returncode != 0
    assert "required_metadata" in completed.stderr


def test_python_and_powershell_reject_unsupported_artifact_kinds(
    tmp_path: Path,
) -> None:
    payload = json.loads(
        (REPO_ROOT / "config" / "live-document-contract.json").read_text(
            encoding="utf-8"
        )
    )
    payload["artifact_sink"]["required_artifacts"].append("audit")
    payload["artifact_sink"]["artifact_paths"]["audit"] = "audit.json"
    malformed_repo = tmp_path / "unsupported-artifact-kind"
    config_root = malformed_repo / "config"
    config_root.mkdir(parents=True)
    (config_root / "live-document-contract.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unsupported artifact kinds"):
        LiveGovernanceContract.model_validate(payload)

    completed = subprocess.run(
        [
            _powershell(),
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            _dot_source_common()
            + "Get-VibeLiveGovernanceContract "
            + f"-RepoRoot {_ps_quote(malformed_repo)}",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
        check=False,
        timeout=RUNTIME_INVOCATION_TIMEOUT_SECONDS,
    )
    assert completed.returncode != 0
    assert "unsupported" in completed.stderr
