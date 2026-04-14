import mimetypes
from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.auth import get_current_user
from core.database import get_db
from models import GithubIntegration, Project
from schemas import (
    ArtifactOut,
    ArtifactPreviewOut,
    GithubIntegrationOut,
    GithubIntegrationUpsert,
    GithubPublishRequest,
    GithubPublishResult,
)
from services.github_service import GithubPublishError, fetch_repo_info, publish_artifact_to_repo
from services.minio_service import download_file, list_file_objects

router = APIRouter(prefix="/projects", tags=["artifacts"])


def _ensure_project_path(project_id: str, path: str) -> str:
    normalized = path.replace("\\", "/").strip().strip("/")
    if not normalized.startswith(f"{project_id}/"):
        raise HTTPException(status_code=400, detail="Artifact path must belong to the current project.")
    return normalized


@router.get("/{project_id}/artifacts", response_model=list[ArtifactOut])
async def list_project_artifacts(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    items = list_file_objects("projects", prefix=f"{project_id}/")
    items.sort(key=lambda item: item.get("last_modified") or "", reverse=True)
    return [
        ArtifactOut(
            path=item["path"],
            filename=PurePosixPath(item["path"]).name,
            agent_id=PurePosixPath(item["path"]).parts[1] if len(PurePosixPath(item["path"]).parts) > 2 else None,
            size=item.get("size", 0),
            last_modified=item.get("last_modified"),
            content_type=item.get("content_type"),
        )
        for item in items
    ]


@router.get("/{project_id}/artifacts/preview", response_model=ArtifactPreviewOut)
async def preview_project_artifact(
    project_id: str,
    path: str = Query(...),
    max_chars: int = Query(12000, ge=1000, le=50000),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    artifact_path = _ensure_project_path(project_id, path)
    content_type = mimetypes.guess_type(artifact_path)[0] or "text/plain"
    if not (
        content_type.startswith("text/")
        or artifact_path.endswith((".md", ".json", ".yml", ".yaml", ".py", ".ts", ".tsx", ".js", ".html", ".css"))
    ):
        raise HTTPException(status_code=400, detail="Preview is only available for text-based artifacts.")

    raw = download_file("projects", artifact_path)
    text = raw.decode("utf-8", errors="replace")
    truncated = len(text) > max_chars
    return ArtifactPreviewOut(
        path=artifact_path,
        filename=PurePosixPath(artifact_path).name,
        content=text[:max_chars],
        content_type=content_type,
        truncated=truncated,
    )


@router.get("/{project_id}/artifacts/download")
async def download_project_artifact(
    project_id: str,
    path: str = Query(...),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    artifact_path = _ensure_project_path(project_id, path)
    filename = PurePosixPath(artifact_path).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    content = download_file("projects", artifact_path)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{project_id}/github", response_model=GithubIntegrationOut | None)
async def get_github_integration(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(select(GithubIntegration).where(GithubIntegration.project_id == project_id))
    integration = result.scalar_one_or_none()
    if not integration:
        return None
    return GithubIntegrationOut(
        project_id=integration.project_id,
        repo_owner=integration.repo_owner,
        repo_name=integration.repo_name,
        default_branch=integration.default_branch,
        base_path=integration.base_path,
        allowed_artifact_extensions=integration.allowed_artifact_extensions or [],
        blocked_path_patterns=integration.blocked_path_patterns or [],
        is_active=integration.is_active,
        has_token=bool(integration.oauth_token_encrypted),
        repo_url=f"https://github.com/{integration.repo_owner}/{integration.repo_name}",
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )


@router.put("/{project_id}/github", response_model=GithubIntegrationOut)
async def upsert_github_integration(
    project_id: str,
    body: GithubIntegrationUpsert,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    result = await db.execute(select(GithubIntegration).where(GithubIntegration.project_id == project_id))
    integration = result.scalar_one_or_none()

    if integration is None:
        if not body.oauth_token:
            raise HTTPException(status_code=400, detail="OAuth token is required when creating a GitHub integration.")
        integration = GithubIntegration(project_id=project_id, oauth_token_encrypted=body.oauth_token.strip())
        db.add(integration)
    elif body.oauth_token:
        integration.oauth_token_encrypted = body.oauth_token.strip()

    integration.repo_owner = body.repo_owner.strip()
    integration.repo_name = body.repo_name.strip()
    integration.default_branch = body.default_branch.strip() or "main"
    integration.base_path = body.base_path.strip().strip("/")
    integration.allowed_artifact_extensions = body.allowed_artifact_extensions or integration.allowed_artifact_extensions
    integration.blocked_path_patterns = body.blocked_path_patterns or integration.blocked_path_patterns
    integration.is_active = body.is_active

    try:
        await fetch_repo_info(integration)
    except GithubPublishError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await db.commit()
    await db.refresh(integration)
    return GithubIntegrationOut(
        project_id=integration.project_id,
        repo_owner=integration.repo_owner,
        repo_name=integration.repo_name,
        default_branch=integration.default_branch,
        base_path=integration.base_path,
        allowed_artifact_extensions=integration.allowed_artifact_extensions or [],
        blocked_path_patterns=integration.blocked_path_patterns or [],
        is_active=integration.is_active,
        has_token=bool(integration.oauth_token_encrypted),
        repo_url=f"https://github.com/{integration.repo_owner}/{integration.repo_name}",
        created_at=integration.created_at,
        updated_at=integration.updated_at,
    )


@router.post("/{project_id}/github/publish-artifact", response_model=GithubPublishResult)
async def publish_project_artifact_to_github(
    project_id: str,
    body: GithubPublishRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(get_current_user),
):
    result = await db.execute(select(GithubIntegration).where(GithubIntegration.project_id == project_id))
    integration = result.scalar_one_or_none()
    if not integration or not integration.is_active:
        raise HTTPException(status_code=404, detail="GitHub integration is not configured for this project.")

    try:
        data = await publish_artifact_to_repo(
            integration=integration,
            project_id=project_id,
            artifact_path=body.artifact_path,
            target_path=body.target_path,
            commit_message=body.commit_message,
        )
    except GithubPublishError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return GithubPublishResult(**data)
