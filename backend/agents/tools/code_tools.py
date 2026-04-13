"""
Minimal code execution sandbox for structured experiments.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

from agents.tools.registry import ToolParam, ToolResult, tool


@tool(
    name="execute_python",
    description="Run a short Python snippet in a temporary file for analysis or validation.",
    params=[ToolParam("code", "string", "Python code to execute.", required=True)],
    agents=["backend_dev", "qa", "analyst", "finance"],
)
async def execute_python(code: str, ctx) -> ToolResult:
    try:
        with tempfile.TemporaryDirectory(prefix="agent-py-") as temp_dir:
            script_path = Path(temp_dir) / "script.py"
            script_path.write_text(code, encoding="utf-8")
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
            output = stdout.decode("utf-8", errors="replace").strip()
            error = stderr.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                return ToolResult(ok=False, output=output, error=error or f"Exit code {proc.returncode}")
            return ToolResult(ok=True, output=output or "(no output)")
    except asyncio.TimeoutError:
        return ToolResult(ok=False, output="", error="Python execution timed out.")
    except Exception as exc:
        return ToolResult(ok=False, output="", error=str(exc))
