from __future__ import annotations

import json
import posixpath
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit


LIVE_GOVERNANCE_CONTRACT_RELPATH = Path("config/live-document-contract.json")
MAX_LIVE_MARKDOWN_DOCUMENTS = 30
REQUIRED_ARTIFACT_KINDS: tuple[str, ...] = (
    "requirement",
    "plan",
    "status",
    "proof",
)
REQUIRED_ARTIFACT_METADATA: tuple[str, ...] = (
    "commit_sha",
    "execution_environment",
)
REQUIRED_PRIMARY_DOCUMENT_KINDS: tuple[str, ...] = (
    "requirement",
    "plan",
)
ALLOWED_LEGACY_WRITE_MODES = frozenset({"disabled", "dual_write", "explicit"})
REQUIRED_GOVERNED_ROOTS = frozenset({".", "docs", "references"})
ALLOWED_DOCUMENT_LIFECYCLES = frozenset({"live", "transitional", "retained"})
ALLOWED_EXCLUDED_PATHS = frozenset({"THIRD_PARTY_LICENSES.md"})
ALLOWED_EXCLUDED_PREFIXES = frozenset({"references/provenance/"})
PULL_REQUEST_PROOF_RETENTION_DAYS = 30
MAIN_PROOF_RETENTION_DAYS = 90
FORMAL_RELEASE_PROOF_DESTINATION = "github_release"

_SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")
_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
_HTML_LINK_PATTERN = re.compile(r'''href=["']([^"']+)["']''', re.IGNORECASE)


def _normalize_relative_path(value: Any, field_name: str, *, allow_dot: bool = False) -> str:
    normalized = str(value or "").replace("\\", "/").strip()
    if not normalized:
        raise ValueError(f"{field_name} must be a non-empty relative path")
    if normalized == ".":
        if allow_dot:
            return normalized
        raise ValueError(f"{field_name} must name a relative path below '.'")
    if normalized.startswith("/") or _WINDOWS_DRIVE_PATTERN.match(normalized):
        raise ValueError(f"{field_name} must be relative: {normalized}")
    normalized = normalized.rstrip("/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be a safe relative path: {normalized}")
    return path.as_posix()


def _normalize_slug(value: Any, field_name: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _SLUG_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a lowercase identifier: {value}")
    return normalized


def _normalize_unique_strings(values: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list")
    normalized = tuple(str(item or "").strip() for item in values)
    if any(not item for item in normalized):
        raise ValueError(f"{field_name} must not contain empty values")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} must not contain duplicates")
    return normalized


def _normalize_run_id(value: Any, field_name: str = "run_id") -> str:
    normalized = str(value or "").strip()
    if not _RUN_ID_PATTERN.fullmatch(normalized):
        raise ValueError(f"{field_name} must be a safe path segment")
    return normalized


@dataclass(slots=True, frozen=True)
class LiveDocumentEntry:
    document_id: str
    path: str
    owner: str
    lifecycle: str

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> "LiveDocumentEntry":
        lifecycle = str(payload.get("lifecycle") or "").strip().lower()
        if lifecycle not in ALLOWED_DOCUMENT_LIFECYCLES:
            raise ValueError(f"unsupported document lifecycle: {lifecycle}")
        path = _normalize_relative_path(payload.get("path"), "document path")
        if not path.casefold().endswith(".md"):
            raise ValueError(f"live document path must be Markdown: {path}")
        return cls(
            document_id=_normalize_slug(payload.get("id"), "document id"),
            path=path,
            owner=_normalize_slug(payload.get("owner"), "document owner"),
            lifecycle=lifecycle,
        )

    def model_dump(self) -> dict[str, str]:
        return {
            "id": self.document_id,
            "path": self.path,
            "owner": self.owner,
            "lifecycle": self.lifecycle,
        }


@dataclass(slots=True, frozen=True)
class StableEntryLinks:
    source: str
    targets: tuple[str, ...]

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> "StableEntryLinks":
        source = _normalize_relative_path(
            payload.get("source"),
            "stable entry source",
        )
        raw_targets = payload.get("targets")
        if not isinstance(raw_targets, list) or not raw_targets:
            raise ValueError("stable entry targets must be a non-empty list")
        targets = tuple(
            _normalize_relative_path(target, "stable entry target")
            for target in raw_targets
        )
        if len({target.casefold() for target in targets}) != len(targets):
            raise ValueError("stable entry targets must be unique")
        return cls(source=source, targets=targets)

    def model_dump(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "targets": list(self.targets),
        }


@dataclass(slots=True, frozen=True)
class ProofRetentionPolicy:
    pull_request_days: int
    main_and_scheduled_days: int
    formal_release: str

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> "ProofRetentionPolicy":
        pull_request_days = int(payload.get("pull_request_days") or 0)
        main_and_scheduled_days = int(
            payload.get("main_and_scheduled_days") or 0
        )
        formal_release = str(payload.get("formal_release") or "").strip().lower()
        if pull_request_days != PULL_REQUEST_PROOF_RETENTION_DAYS:
            raise ValueError(
                "proof retention for pull requests must be exactly "
                f"{PULL_REQUEST_PROOF_RETENTION_DAYS} days"
            )
        if main_and_scheduled_days != MAIN_PROOF_RETENTION_DAYS:
            raise ValueError(
                "proof retention for main and scheduled runs must be exactly "
                f"{MAIN_PROOF_RETENTION_DAYS} days"
            )
        if formal_release != FORMAL_RELEASE_PROOF_DESTINATION:
            raise ValueError(
                "proof retention for formal releases must use GitHub Release"
            )
        return cls(
            pull_request_days=pull_request_days,
            main_and_scheduled_days=main_and_scheduled_days,
            formal_release=formal_release,
        )

    def model_dump(self) -> dict[str, Any]:
        return {
            "pull_request_days": self.pull_request_days,
            "main_and_scheduled_days": self.main_and_scheduled_days,
            "formal_release": self.formal_release,
        }


@dataclass(slots=True, frozen=True)
class ArtifactSinkContract:
    schema_version: int
    root: str
    required_artifacts: tuple[str, ...]
    required_metadata: tuple[str, ...]
    artifact_paths: tuple[tuple[str, str], ...]
    primary_document_paths: tuple[tuple[str, str], ...]
    manifest_path: str
    legacy_compatibility_path: str
    legacy_documentation_roots: tuple[str, ...]
    legacy_removal_release: str
    legacy_write_mode: str

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> "ArtifactSinkContract":
        schema_version = int(payload.get("schema_version") or 0)
        if schema_version <= 0:
            raise ValueError("artifact sink schema_version must be positive")
        required_artifacts = _normalize_unique_strings(
            payload.get("required_artifacts"),
            "artifact sink required_artifacts",
        )
        missing_artifacts = set(REQUIRED_ARTIFACT_KINDS) - set(required_artifacts)
        if missing_artifacts:
            raise ValueError(
                "artifact sink is missing required artifact kinds: "
                + ", ".join(sorted(missing_artifacts))
            )
        extra_artifacts = set(required_artifacts) - set(REQUIRED_ARTIFACT_KINDS)
        if extra_artifacts:
            raise ValueError(
                "artifact sink contains unsupported artifact kinds: "
                + ", ".join(sorted(extra_artifacts))
            )
        required_metadata = _normalize_unique_strings(
            payload.get("required_metadata"),
            "artifact sink required_metadata",
        )
        missing_metadata = set(REQUIRED_ARTIFACT_METADATA) - set(required_metadata)
        if missing_metadata:
            raise ValueError(
                "artifact sink is missing required metadata: "
                + ", ".join(sorted(missing_metadata))
            )
        raw_artifact_paths = payload.get("artifact_paths")
        if isinstance(raw_artifact_paths, dict):
            artifact_paths = tuple(
                (
                    str(kind).strip(),
                    _normalize_relative_path(path, f"artifact path for {kind}"),
                )
                for kind, path in raw_artifact_paths.items()
            )
        else:
            raise ValueError("artifact sink artifact_paths must be an object")
        artifact_path_kinds = [kind for kind, _ in artifact_paths]
        if any(not kind for kind in artifact_path_kinds):
            raise ValueError("artifact sink artifact_paths must use non-empty kinds")
        if len(set(artifact_path_kinds)) != len(artifact_path_kinds):
            raise ValueError("artifact sink artifact_paths must use unique kinds")
        missing_path_kinds = set(required_artifacts) - set(artifact_path_kinds)
        if missing_path_kinds:
            raise ValueError(
                "artifact sink artifact_paths is missing required kinds: "
                + ", ".join(sorted(missing_path_kinds))
            )
        extra_path_kinds = set(artifact_path_kinds) - set(required_artifacts)
        if extra_path_kinds:
            raise ValueError(
                "artifact sink artifact_paths contains undeclared kinds: "
                + ", ".join(sorted(extra_path_kinds))
            )
        if len({path.casefold() for _, path in artifact_paths}) != len(artifact_paths):
            raise ValueError("artifact sink artifact_paths must use unique paths")
        raw_primary_document_paths = payload.get("primary_document_paths")
        if not isinstance(raw_primary_document_paths, dict):
            raise ValueError(
                "artifact sink primary_document_paths must be an object"
            )
        primary_document_paths = tuple(
            (
                str(kind).strip(),
                _normalize_relative_path(
                    path,
                    f"primary document path for {kind}",
                ),
            )
            for kind, path in raw_primary_document_paths.items()
        )
        primary_document_kinds = [kind for kind, _ in primary_document_paths]
        if set(primary_document_kinds) != set(REQUIRED_PRIMARY_DOCUMENT_KINDS):
            raise ValueError(
                "artifact sink primary_document_paths must define exactly: "
                + ", ".join(REQUIRED_PRIMARY_DOCUMENT_KINDS)
            )
        if len(primary_document_kinds) != len(set(primary_document_kinds)):
            raise ValueError(
                "artifact sink primary_document_paths must use unique kinds"
            )
        if len({path.casefold() for _, path in primary_document_paths}) != len(
            primary_document_paths
        ):
            raise ValueError(
                "artifact sink primary_document_paths must use unique paths"
            )
        manifest_path = _normalize_relative_path(
            payload.get("manifest_path"),
            "artifact sink manifest_path",
        )
        legacy_compatibility_path = _normalize_relative_path(
            payload.get("legacy_compatibility_path"),
            "artifact sink legacy_compatibility_path",
        )
        all_contract_paths = [path for _, path in artifact_paths]
        all_contract_paths.extend(path for _, path in primary_document_paths)
        all_contract_paths.append(manifest_path)
        all_contract_paths.append(legacy_compatibility_path)
        if len(all_contract_paths) != len(
            {path.casefold() for path in all_contract_paths}
        ):
            raise ValueError(
                "artifact sink artifact, primary document, and manifest paths must be distinct"
            )
        raw_legacy_roots = payload.get("legacy_documentation_roots")
        if not isinstance(raw_legacy_roots, list):
            raise ValueError(
                "artifact sink legacy_documentation_roots must be a list"
            )
        legacy_documentation_roots = tuple(
            _normalize_relative_path(path, "legacy documentation root")
            for path in raw_legacy_roots
        )
        if len(legacy_documentation_roots) != len(
            REQUIRED_PRIMARY_DOCUMENT_KINDS
        ):
            raise ValueError(
                "artifact sink legacy_documentation_roots must map requirement and plan"
            )
        if len({root.casefold() for root in legacy_documentation_roots}) != len(
            legacy_documentation_roots
        ):
            raise ValueError(
                "artifact sink legacy_documentation_roots must be unique"
            )
        legacy_removal_release = str(
            payload.get("legacy_removal_release") or ""
        ).strip()
        if not legacy_removal_release:
            raise ValueError("artifact sink legacy_removal_release must be non-empty")
        legacy_write_mode = str(
            payload.get("legacy_write_mode") or ""
        ).strip().lower()
        if legacy_write_mode not in ALLOWED_LEGACY_WRITE_MODES:
            raise ValueError(
                "unsupported artifact sink legacy_write_mode: " + legacy_write_mode
            )
        return cls(
            schema_version=schema_version,
            root=_normalize_relative_path(payload.get("root"), "artifact sink root"),
            required_artifacts=required_artifacts,
            required_metadata=required_metadata,
            artifact_paths=artifact_paths,
            primary_document_paths=primary_document_paths,
            manifest_path=manifest_path,
            legacy_compatibility_path=legacy_compatibility_path,
            legacy_documentation_roots=legacy_documentation_roots,
            legacy_removal_release=legacy_removal_release,
            legacy_write_mode=legacy_write_mode,
        )

    @property
    def artifact_path_map(self) -> dict[str, str]:
        return dict(self.artifact_paths)

    @property
    def primary_document_path_map(self) -> dict[str, str]:
        return dict(self.primary_document_paths)

    @property
    def legacy_documentation_root_map(self) -> dict[str, str]:
        return dict(
            zip(
                REQUIRED_PRIMARY_DOCUMENT_KINDS,
                self.legacy_documentation_roots,
                strict=True,
            )
        )

    def resolve_run_root(self, workspace_root: str | Path, run_id: str) -> Path:
        workspace = Path(workspace_root).resolve()
        normalized_run_id = _normalize_run_id(run_id)
        run_root = (workspace / Path(self.root) / normalized_run_id).resolve()
        if not run_root.is_relative_to(workspace):
            raise ValueError("run artifact root resolves outside the governed workspace")
        return run_root

    def resolve_run_artifact_paths(
        self,
        workspace_root: str | Path,
        run_id: str,
    ) -> dict[str, Path]:
        run_root = self.resolve_run_root(workspace_root, run_id)
        paths = {
            kind: (run_root / Path(path)).resolve()
            for kind, path in self.artifact_paths
        }
        paths["manifest"] = (run_root / Path(self.manifest_path)).resolve()
        paths["legacy_compatibility"] = (
            run_root / Path(self.legacy_compatibility_path)
        ).resolve()
        for kind, path in paths.items():
            if not path.is_relative_to(run_root):
                raise ValueError(f"artifact path resolves outside the run root: {kind}")
        return paths

    def resolve_run_primary_document_paths(
        self,
        workspace_root: str | Path,
        run_id: str,
    ) -> dict[str, Path]:
        run_root = self.resolve_run_root(workspace_root, run_id)
        paths = {
            kind: (run_root / Path(path)).resolve()
            for kind, path in self.primary_document_paths
        }
        for kind, path in paths.items():
            if not path.is_relative_to(run_root):
                raise ValueError(
                    f"primary document path resolves outside the run root: {kind}"
                )
        return paths

    def model_dump(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "root": self.root,
            "required_artifacts": list(self.required_artifacts),
            "required_metadata": list(self.required_metadata),
            "artifact_paths": self.artifact_path_map,
            "primary_document_paths": self.primary_document_path_map,
            "manifest_path": self.manifest_path,
            "legacy_compatibility_path": self.legacy_compatibility_path,
            "legacy_documentation_roots": list(self.legacy_documentation_roots),
            "legacy_removal_release": self.legacy_removal_release,
            "legacy_write_mode": self.legacy_write_mode,
        }


@dataclass(slots=True, frozen=True)
class RunArtifactManifest:
    schema_version: int
    run_id: str
    artifact_root: str
    artifacts: dict[str, str]
    commit_sha: str
    execution_environment: dict[str, str]
    legacy_compatibility: dict[str, Any]

    @classmethod
    def model_validate(
        cls,
        payload: dict[str, Any],
        artifact_sink: ArtifactSinkContract,
    ) -> "RunArtifactManifest":
        schema_version = int(payload.get("schema_version") or 0)
        if schema_version != artifact_sink.schema_version:
            raise ValueError(
                "run artifact schema_version does not match the artifact sink contract"
            )
        run_id = _normalize_run_id(payload.get("run_id"), "run artifact manifest run_id")
        raw_artifacts = payload.get("artifacts")
        if not isinstance(raw_artifacts, dict):
            raise ValueError("run artifact manifest artifacts must be an object")
        artifacts = {
            str(key): _normalize_relative_path(value, f"artifact path for {key}")
            for key, value in raw_artifacts.items()
        }
        missing_artifacts = set(artifact_sink.required_artifacts) - set(artifacts)
        if missing_artifacts:
            raise ValueError(
                "run artifact manifest is missing artifacts: "
                + ", ".join(sorted(missing_artifacts))
            )
        if len({path.casefold() for path in artifacts.values()}) != len(artifacts):
            raise ValueError("run artifact paths must be unique")
        if artifacts != artifact_sink.artifact_path_map:
            raise ValueError(
                "run artifact manifest paths must match the artifact sink contract"
            )
        commit_sha = str(payload.get("commit_sha") or "").strip()
        if not commit_sha:
            raise ValueError("run artifact manifest requires commit_sha")
        raw_environment = payload.get("execution_environment")
        if not isinstance(raw_environment, dict) or not raw_environment:
            raise ValueError(
                "run artifact manifest requires execution_environment metadata"
            )
        execution_environment = {
            str(key).strip(): str(value).strip()
            for key, value in raw_environment.items()
            if str(key).strip() and str(value).strip()
        }
        if not execution_environment:
            raise ValueError(
                "run artifact manifest requires execution_environment metadata"
            )
        artifact_root = _normalize_relative_path(
            payload.get("artifact_root"),
            "run artifact root",
        )
        artifact_sink_prefix = artifact_sink.root.rstrip("/") + "/"
        if not artifact_root.startswith(artifact_sink_prefix):
            raise ValueError(
                "run artifact root must be a child of the artifact sink root: "
                f"{artifact_sink.root}"
            )
        expected_artifact_root = (
            PurePosixPath(artifact_sink.root) / run_id
        ).as_posix()
        if artifact_root != expected_artifact_root:
            raise ValueError(
                "run artifact root must match artifact sink root and run_id"
            )
        raw_legacy_compatibility = payload.get("legacy_compatibility")
        if not isinstance(raw_legacy_compatibility, dict):
            raise ValueError("legacy_compatibility must be an object")
        legacy_compatibility = dict(raw_legacy_compatibility)
        if (
            str(legacy_compatibility.get("mode") or "").strip().lower()
            != artifact_sink.legacy_write_mode
        ):
            raise ValueError(
                "legacy compatibility mode must match the artifact sink contract"
            )
        if (
            str(legacy_compatibility.get("removal_release") or "").strip()
            != artifact_sink.legacy_removal_release
        ):
            raise ValueError(
                "legacy compatibility removal_release must match the artifact sink contract"
            )
        raw_documentation_roots = legacy_compatibility.get("documentation_roots")
        if not isinstance(raw_documentation_roots, list) or tuple(
            str(root).replace("\\", "/").strip()
            for root in raw_documentation_roots
        ) != artifact_sink.legacy_documentation_roots:
            raise ValueError(
                "legacy compatibility documentation_roots must match the artifact sink contract"
            )
        raw_writes = legacy_compatibility.get("writes")
        if not isinstance(raw_writes, list) or any(
            not str(path or "").strip() for path in raw_writes
        ):
            raise ValueError("legacy compatibility writes must be a list of paths")
        if artifact_sink.legacy_write_mode == "disabled" and raw_writes:
            raise ValueError(
                "disabled legacy compatibility cannot declare writes"
            )
        if legacy_compatibility.get("observable") is not True:
            raise ValueError("legacy compatibility must be observable")
        legacy_compatibility = {
            "mode": artifact_sink.legacy_write_mode,
            "removal_release": artifact_sink.legacy_removal_release,
            "documentation_roots": list(artifact_sink.legacy_documentation_roots),
            "writes": [str(path).strip() for path in raw_writes],
            "observable": True,
        }
        return cls(
            schema_version=schema_version,
            run_id=run_id,
            artifact_root=artifact_root,
            artifacts=artifacts,
            commit_sha=commit_sha,
            execution_environment=execution_environment,
            legacy_compatibility=legacy_compatibility,
        )

    def model_dump(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "artifact_root": self.artifact_root,
            "artifacts": dict(self.artifacts),
            "commit_sha": self.commit_sha,
            "execution_environment": dict(self.execution_environment),
            "legacy_compatibility": dict(self.legacy_compatibility),
        }

    def resolve_artifact_paths(
        self,
        workspace_root: str | Path,
    ) -> dict[str, Path]:
        workspace = Path(workspace_root).resolve()
        run_root = (workspace / Path(self.artifact_root)).resolve()
        if not run_root.is_relative_to(workspace):
            raise ValueError(
                "run artifact root resolves outside the governed workspace"
            )
        resolved_paths: dict[str, Path] = {}
        for artifact_kind, artifact_relpath in self.artifacts.items():
            artifact_path = (run_root / Path(artifact_relpath)).resolve()
            if not artifact_path.is_relative_to(run_root):
                raise ValueError(
                    f"artifact path resolves outside the run root: {artifact_kind}"
                )
            resolved_paths[artifact_kind] = artifact_path
        return resolved_paths


@dataclass(slots=True, frozen=True)
class LiveGovernanceContract:
    schema_version: int
    max_live_documents: int
    governed_roots: tuple[str, ...]
    excluded_paths: tuple[str, ...]
    excluded_prefixes: tuple[str, ...]
    documents: tuple[LiveDocumentEntry, ...]
    stable_entry_links: tuple[StableEntryLinks, ...]
    proof_retention: ProofRetentionPolicy
    artifact_sink: ArtifactSinkContract

    @classmethod
    def model_validate(cls, payload: dict[str, Any]) -> "LiveGovernanceContract":
        schema_version = int(payload.get("schema_version") or 0)
        if schema_version <= 0:
            raise ValueError("live governance schema_version must be positive")
        max_live_documents = int(payload.get("max_live_documents") or 0)
        if max_live_documents <= 0 or max_live_documents > MAX_LIVE_MARKDOWN_DOCUMENTS:
            raise ValueError(
                f"max_live_documents must be between 1 and {MAX_LIVE_MARKDOWN_DOCUMENTS}"
            )
        raw_roots = payload.get("governed_roots")
        if not isinstance(raw_roots, list) or not raw_roots:
            raise ValueError("governed_roots must be a non-empty list")
        governed_roots = tuple(
            _normalize_relative_path(root, "governed root", allow_dot=True)
            for root in raw_roots
        )
        missing_roots = REQUIRED_GOVERNED_ROOTS - set(governed_roots)
        if missing_roots:
            raise ValueError(
                "missing required governed roots: "
                + ", ".join(sorted(missing_roots))
            )
        excluded_paths = tuple(
            _normalize_relative_path(path, "excluded path")
            for path in list(payload.get("excluded_paths") or [])
        )
        excluded_prefixes = tuple(
            _normalize_relative_path(path, "excluded prefix").rstrip("/") + "/"
            for path in list(payload.get("excluded_prefixes") or [])
        )
        unsupported_excluded_paths = set(excluded_paths) - ALLOWED_EXCLUDED_PATHS
        if unsupported_excluded_paths:
            raise ValueError(
                "unsupported excluded path: "
                + ", ".join(sorted(unsupported_excluded_paths))
            )
        unsupported_excluded_prefixes = (
            set(excluded_prefixes) - ALLOWED_EXCLUDED_PREFIXES
        )
        if unsupported_excluded_prefixes:
            raise ValueError(
                "unsupported excluded prefix: "
                + ", ".join(sorted(unsupported_excluded_prefixes))
            )
        if len({path.casefold() for path in excluded_paths}) != len(excluded_paths):
            raise ValueError("excluded paths must be unique")
        if len({path.casefold() for path in excluded_prefixes}) != len(
            excluded_prefixes
        ):
            raise ValueError("excluded prefixes must be unique")
        raw_documents = payload.get("documents")
        if not isinstance(raw_documents, list):
            raise ValueError("documents must be a list")
        if not raw_documents:
            raise ValueError("documents must contain at least one live document")
        documents = tuple(
            LiveDocumentEntry.model_validate(dict(document))
            for document in raw_documents
            if isinstance(document, dict)
        )
        if len(documents) != len(raw_documents):
            raise ValueError("every live document entry must be an object")
        if len(documents) > max_live_documents:
            raise ValueError(
                f"live document registry contains {len(documents)} entries; "
                f"the configured budget is {max_live_documents}"
            )
        document_ids = [document.document_id for document in documents]
        document_paths = [document.path for document in documents]
        if len(set(document_ids)) != len(document_ids):
            raise ValueError("live document ids must be unique")
        if len(set(document_paths)) != len(document_paths):
            raise ValueError("live document paths must be unique")
        for document in documents:
            if document.path in excluded_paths or any(
                document.path.startswith(prefix) for prefix in excluded_prefixes
            ):
                raise ValueError(
                    f"excluded document cannot be registered as live: {document.path}"
                )
            if not _is_path_under_governed_roots(document.path, governed_roots):
                raise ValueError(
                    f"live document is outside governed roots: {document.path}"
                )
        raw_stable_entry_links = payload.get("stable_entry_links")
        if not isinstance(raw_stable_entry_links, list) or not raw_stable_entry_links:
            raise ValueError("stable_entry_links must be a non-empty list")
        stable_entry_links = tuple(
            StableEntryLinks.model_validate(dict(entry))
            for entry in raw_stable_entry_links
            if isinstance(entry, dict)
        )
        if len(stable_entry_links) != len(raw_stable_entry_links):
            raise ValueError("every stable entry link declaration must be an object")
        stable_sources = [entry.source for entry in stable_entry_links]
        if len({source.casefold() for source in stable_sources}) != len(stable_sources):
            raise ValueError("stable entry sources must be unique")
        registered_paths = {path.casefold() for path in document_paths}
        for entry in stable_entry_links:
            if entry.source.casefold() not in registered_paths:
                raise ValueError(
                    f"stable entry source must be registered: {entry.source}"
                )
            for target in entry.targets:
                if target.casefold() not in registered_paths:
                    raise ValueError(
                        f"stable entry target must be registered: {target}"
                    )
        raw_proof_retention = payload.get("proof_retention")
        if not isinstance(raw_proof_retention, dict):
            raise ValueError("proof_retention must be an object")
        raw_artifact_sink = payload.get("artifact_sink")
        if not isinstance(raw_artifact_sink, dict):
            raise ValueError("artifact_sink must be an object")
        return cls(
            schema_version=schema_version,
            max_live_documents=max_live_documents,
            governed_roots=governed_roots,
            excluded_paths=excluded_paths,
            excluded_prefixes=excluded_prefixes,
            documents=documents,
            stable_entry_links=stable_entry_links,
            proof_retention=ProofRetentionPolicy.model_validate(raw_proof_retention),
            artifact_sink=ArtifactSinkContract.model_validate(raw_artifact_sink),
        )

    def validate_run_artifact_manifest(
        self,
        payload: dict[str, Any],
    ) -> RunArtifactManifest:
        return RunArtifactManifest.model_validate(payload, self.artifact_sink)

    def model_dump(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "max_live_documents": self.max_live_documents,
            "governed_roots": list(self.governed_roots),
            "excluded_paths": list(self.excluded_paths),
            "excluded_prefixes": list(self.excluded_prefixes),
            "documents": [document.model_dump() for document in self.documents],
            "stable_entry_links": [
                entry.model_dump() for entry in self.stable_entry_links
            ],
            "proof_retention": self.proof_retention.model_dump(),
            "artifact_sink": self.artifact_sink.model_dump(),
        }


def _is_path_under_governed_roots(
    document_path: str,
    governed_roots: tuple[str, ...],
) -> bool:
    for root in governed_roots:
        if root == "." and "/" not in document_path:
            return True
        if root != "." and document_path.startswith(root.rstrip("/") + "/"):
            return True
    return False


def resolve_live_governance_contract_path(start_path: str | Path) -> Path:
    current = Path(start_path).resolve()
    if current.is_file():
        current = current.parent
    while True:
        candidate = current / LIVE_GOVERNANCE_CONTRACT_RELPATH
        if candidate.exists():
            return candidate
        if current.parent == current:
            break
        current = current.parent
    raise RuntimeError(
        f"live governance contract not found from start path: {start_path}"
    )


def load_live_governance_contract_file(
    contract_path: str | Path,
) -> LiveGovernanceContract:
    payload = json.loads(
        Path(contract_path).read_text(encoding="utf-8-sig")
    )
    if not isinstance(payload, dict):
        raise ValueError("live governance contract must be a JSON object")
    return LiveGovernanceContract.model_validate(payload)


def load_live_governance_contract(
    start_path: str | Path,
) -> LiveGovernanceContract:
    return load_live_governance_contract_file(
        resolve_live_governance_contract_path(start_path)
    )


def validate_live_document_workspace(
    contract: LiveGovernanceContract,
    repo_root: str | Path,
) -> list[Path]:
    root = Path(repo_root).resolve()
    validated_paths: list[Path] = []
    for document in contract.documents:
        path = root / Path(document.path)
        if not path.is_file():
            raise ValueError(f"registered live document does not exist: {document.path}")
        validated_paths.append(path)
    for entry in contract.stable_entry_links:
        source_path = root / Path(entry.source)
        linked_targets = _resolve_markdown_link_targets(
            source_path.read_text(encoding="utf-8-sig"),
            entry.source,
        )
        for target in entry.targets:
            if target.casefold() not in linked_targets:
                raise ValueError(
                    "stable entry link is missing: "
                    f"{entry.source} -> {target}"
                )
    return validated_paths


def _resolve_markdown_link_targets(markdown: str, source: str) -> set[str]:
    source_parent = PurePosixPath(source).parent.as_posix()
    resolved_targets: set[str] = set()
    raw_destinations = [
        match.group(1).strip() for match in _MARKDOWN_LINK_PATTERN.finditer(markdown)
    ]
    raw_destinations.extend(
        match.group(1).strip() for match in _HTML_LINK_PATTERN.finditer(markdown)
    )
    for raw_destination in raw_destinations:
        if not raw_destination:
            continue
        if raw_destination.startswith("<") and ">" in raw_destination:
            raw_destination = raw_destination[1 : raw_destination.index(">")]
        else:
            raw_destination = raw_destination.split(maxsplit=1)[0]
        parsed = urlsplit(raw_destination)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        decoded_path = unquote(parsed.path).replace("\\", "/")
        if decoded_path.startswith("/") or _WINDOWS_DRIVE_PATTERN.match(decoded_path):
            continue
        resolved = posixpath.normpath(
            posixpath.join(source_parent, decoded_path)
        )
        if resolved == "." or resolved == ".." or resolved.startswith("../"):
            continue
        resolved_targets.add(PurePosixPath(resolved).as_posix().casefold())
    return resolved_targets


def validate_live_document_changes(
    contract: LiveGovernanceContract,
    added_paths: list[str] | tuple[str, ...],
) -> list[str]:
    registered_paths = {
        document.path.casefold(): document.path for document in contract.documents
    }
    validated_paths: list[str] = []
    unregistered_paths: list[str] = []
    for raw_path in added_paths:
        path = _normalize_relative_path(raw_path, "added path")
        if not path.casefold().endswith(".md"):
            continue
        if not _is_path_under_governed_roots(path, contract.governed_roots):
            continue
        if path.casefold() in {value.casefold() for value in contract.excluded_paths}:
            continue
        if any(
            path.casefold().startswith(prefix.casefold())
            for prefix in contract.excluded_prefixes
        ):
            continue
        registered_path = registered_paths.get(path.casefold())
        if registered_path is None:
            unregistered_paths.append(path)
        else:
            validated_paths.append(registered_path)
    if unregistered_paths:
        raise ValueError(
            "new governed Markdown is not registered: "
            + ", ".join(sorted(unregistered_paths))
        )
    return validated_paths


def validate_live_document_registry_transition(
    contract: LiveGovernanceContract,
    previous_document_paths: list[str] | tuple[str, ...],
    repo_root: str | Path,
) -> list[str]:
    current_paths = {document.path.casefold() for document in contract.documents}
    previous_paths = {
        _normalize_relative_path(path, "previous live document path")
        for path in previous_document_paths
    }
    removed_paths = sorted(
        path for path in previous_paths if path.casefold() not in current_paths
    )
    root = Path(repo_root).resolve()
    lingering_paths = [path for path in removed_paths if (root / Path(path)).exists()]
    if lingering_paths:
        raise ValueError(
            "document removed from the registry still exists in the workspace: "
            + ", ".join(lingering_paths)
        )
    return removed_paths


def validate_run_artifact_workspace(
    manifest: RunArtifactManifest,
    workspace_root: str | Path,
) -> dict[str, Path]:
    artifact_paths = manifest.resolve_artifact_paths(workspace_root)
    missing_artifacts = [
        artifact_kind
        for artifact_kind, artifact_path in artifact_paths.items()
        if not artifact_path.is_file()
    ]
    if missing_artifacts:
        raise ValueError(
            "run artifact files are missing: "
            + ", ".join(sorted(missing_artifacts))
        )
    return artifact_paths
