"""
GitHub tools for publishing safe project artifacts.
"""
from __future__ import annotations

from pathlib import PurePosixPath

from sqlalchemy import select

from agents.tools.registry import ToolParam, ToolResult, tool
from core.database import AsyncSessionLocal
from models import GithubIntegration
from services.github_service import GithubPublishError, publish_artifact_to_repo
from services.minio_service import list_file_objects


@tool(
    name="list_project_artifacts",
    description="List saved project artifacts that can be reviewed or published.",
    params=[],
    agents=["director", "backend_dev", "frontend_dev", "ux_ui", "devops", "marketer", "copywriter", "seo", "smm"],
)
async def list_project_artifacts(ctx) -> ToolResult:
    if not ctx.project_id:
        return ToolResult(ok=False, output="", error="Current task has no project_id.")
    try:
        items = list_file_objects("projects", prefix=f"{ctx.project_id}/")
        items.sort(key=lambda item: item.get("last_modified") or "", reverse=True)
        if not items:
            return ToolResult(ok=True, output="No project artifacts have been saved yet.", data=[])
        lines = ["Available project artifacts:"]
        data = []
        for item in items[:20]:
            path = item["path"]
            filename = PurePosixPath(path).name
            agent_id = PurePosixPath(path).parts[1] if len(PurePosixPath(path).parts) > 2 else "unknown"
            size = item.get("size", 0)
            lines.append(f"- {filename} | {agent_id} | {path} | {size} bytes")
            data.append(item)
        return ToolResult(ok=True, output="\n".join(lines), data=data)
    except Exception as exc:
        return ToolResult(ok=False, output="", error=str(exc))


@tool(
    name="publish_artifact_to_github",
    description="Publish a saved project artifact to the configured GitHub repository using a safe target path.",
    params=[
        ToolParam("artifact_path", "string", "Artifact path from project storage.", required=True),
        ToolParam("target_path", "string", "Repository-relative target path under the configured base path.", required=False),
        ToolParam("commit_message", "string", "Commit message for the publish action.", required=False),
    ],
    agents=["director", "backend_dev", "frontend_dev", "ux_ui", "devops", "marketer", "copywriter", "seo", "smm"],
)
async def publish_artifact_to_github(
    artifact_path: str,
    ctx,
    target_path: str = "",
    commit_message: str = "Publish generated artifact from AI DevStudio",
) -> ToolResult:
    if not ctx.project_id:
        return ToolResult(ok=False, output="", error="Current task has no project_id.")

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(GithubIntegration).where(GithubIntegration.project_id == ctx.project_id))
            integration = result.scalar_one_or_none()
            if not integration or not integration.is_active:
                return ToolResult(ok=False, output="", error="GitHub integration is not configured for this project.")

        published = await publish_artifact_to_repo(
            integration=integration,
            project_id=ctx.project_id,
            artifact_path=artifact_path,
            target_path=target_path or None,
            commit_message=commit_message,
        )
        return ToolResult(
            ok=True,
            output=f"Published {artifact_path} to GitHub: {published['html_url']}",
            data=published,
        )
    except GithubPublishError as exc:
        return ToolResult(ok=False, output="", error=str(exc))
    except Exception as exc:
        return ToolResult(ok=False, output="", error=str(exc))
