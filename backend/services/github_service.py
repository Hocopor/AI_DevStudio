from __future__ import annotations

import base64
import fnmatch
from pathlib import PurePosixPath
from typing import Optional

import httpx

from models import GithubIntegration
from services.minio_service import download_file


class GithubPublishError(Exception):
    pass


def _normalize_path(path: str) -> str:
    cleaned = (path or "").replace("\\", "/").strip().strip("/")
    if not cleaned:
        raise GithubPublishError("Path cannot be empty.")
    normalized = PurePosixPath(cleaned)
    path_str = str(normalized)
    if path_str == "." or path_str.startswith("../") or "/../" in path_str:
        raise GithubPublishError("Unsafe path.")
    return path_str


def _is_blocked(path: str, patterns: list[str]) -> bool:
    lowered = path.lower()
    for pattern in patterns:
        if fnmatch.fnmatch(lowered, pattern.lower()):
            return True
    return False


def _is_allowed_extension(path: str, allowed_extensions: list[str]) -> bool:
    if not allowed_extensions:
        return True
    suffixes = PurePosixPath(path).suffixes
    if not suffixes:
        return PurePosixPath(path).name.lower() in {"dockerfile", ".gitignore"}
    joined = "".join(suffixes).lower()
    return any(joined.endswith(ext.lower()) for ext in allowed_extensions)


def ensure_safe_target_path(target_path: str, integration: GithubIntegration) -> str:
    normalized = _normalize_path(target_path)
    base = _normalize_path(integration.base_path) if integration.base_path else ""
    full_path = f"{base}/{normalized}".strip("/") if base else normalized

    if _is_blocked(full_path, integration.blocked_path_patterns or []):
        raise GithubPublishError(f"Blocked publish path: {full_path}")
    if not _is_allowed_extension(full_path, integration.allowed_artifact_extensions or []):
        raise GithubPublishError(f"File extension is not allowed for publish: {full_path}")
    return full_path


async def fetch_repo_info(integration: GithubIntegration) -> dict:
    url = f"https://api.github.com/repos/{integration.repo_owner}/{integration.repo_name}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {integration.oauth_token_encrypted}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code >= 400:
        raise GithubPublishError(f"GitHub repo access failed: HTTP {resp.status_code}")
    return resp.json()


async def _get_existing_sha(integration: GithubIntegration, target_path: str) -> Optional[str]:
    url = f"https://api.github.com/repos/{integration.repo_owner}/{integration.repo_name}/contents/{target_path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {integration.oauth_token_encrypted}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {"ref": integration.default_branch}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=headers, params=params)
    if resp.status_code == 404:
        return None
    if resp.status_code >= 400:
        raise GithubPublishError(f"GitHub content lookup failed: HTTP {resp.status_code}")
    payload = resp.json()
    return payload.get("sha")


async def publish_artifact_to_repo(
    integration: GithubIntegration,
    project_id: str,
    artifact_path: str,
    target_path: Optional[str],
    commit_message: str,
) -> dict:
    project_prefix = f"{project_id}/"
    artifact_path = _normalize_path(artifact_path)
    if not artifact_path.startswith(project_prefix):
        raise GithubPublishError("Artifact path does not belong to this project.")
    if _is_blocked(artifact_path, integration.blocked_path_patterns or []):
        raise GithubPublishError(f"Blocked artifact path: {artifact_path}")

    filename = PurePosixPath(artifact_path).name
    target = ensure_safe_target_path(target_path or filename, integration)
    content = download_file("projects", artifact_path)

    existing_sha = await _get_existing_sha(integration, target)
    payload = {
        "message": commit_message.strip() or "Publish generated artifact from AI DevStudio",
        "content": base64.b64encode(content).decode("ascii"),
        "branch": integration.default_branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {integration.oauth_token_encrypted}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    url = f"https://api.github.com/repos/{integration.repo_owner}/{integration.repo_name}/contents/{target}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(url, headers=headers, json=payload)
    if resp.status_code >= 400:
        raise GithubPublishError(f"GitHub publish failed: HTTP {resp.status_code} {resp.text[:300]}")

    data = resp.json()
    content_info = data.get("content", {})
    commit_info = data.get("commit", {})
    return {
        "commit_sha": commit_info.get("sha", ""),
        "target_path": target,
        "repo_url": f"https://github.com/{integration.repo_owner}/{integration.repo_name}",
        "html_url": content_info.get("html_url")
        or f"https://github.com/{integration.repo_owner}/{integration.repo_name}/blob/{integration.default_branch}/{target}",
        "branch": integration.default_branch,
    }
