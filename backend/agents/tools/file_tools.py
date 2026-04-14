"""
File tools for saving task artifacts.
"""
from __future__ import annotations

from agents.context import get_pcd, save_pcd
from agents.tools.registry import ToolParam, ToolResult, tool


@tool(
    name="write_file",
    description=(
        "Save a durable project artifact to storage. "
        "You MUST provide `filename` and `content`. "
        "Always include a filename with an extension, for example: `brief.md`, `landing-copy.md`, "
        "`api-spec.yaml`, `deployment-checklist.md`, `result.json`, `wireframe.html`."
    ),
    params=[
        ToolParam(
            "filename",
            "string",
            "Required. Filename with extension only, for example `brief.md` or `api-spec.yaml`.",
            required=True,
        ),
        ToolParam(
            "content",
            "string",
            "Required. Full file content to save under the filename.",
            required=True,
        ),
        ToolParam(
            "description",
            "string",
            "Optional short explanation of what this file contains and why it matters.",
            required=False,
        ),
    ],
)
async def write_file(filename: str, content: str, ctx, description: str = "") -> ToolResult:
    try:
        from services.minio_service import save_agent_artifact

        if not ctx.project_id:
            return ToolResult(ok=False, output="", error="Current task has no project_id.")

        path = save_agent_artifact(
            project_id=ctx.project_id,
            agent_id=ctx.agent_id,
            filename=filename,
            data=content.encode("utf-8"),
            content_type="text/plain",
        )

        pcd = await get_pcd(ctx.project_id)
        pcd.set_artifact(ctx.agent_id, path)
        if description:
            pcd.add_event(f"{ctx.agent_name} saved artifact {filename}: {description}")
        await save_pcd(pcd)

        return ToolResult(ok=True, output=f"Artifact saved to {path}", data={"path": path})
    except Exception as exc:
        return ToolResult(ok=False, output="", error=str(exc))
