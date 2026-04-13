from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime


# ──────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────
class LoginRequest(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ──────────────────────────────────────────────
# PROJECTS
# ──────────────────────────────────────────────
class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    goal: Optional[str] = None
    target_audience: Optional[str] = None
    monetization_model: Optional[str] = None
    autonomy_mode: str = "stage_approval"
    approval_triggers: dict = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    goal: Optional[str] = None
    target_audience: Optional[str] = None
    monetization_model: Optional[str] = None
    autonomy_mode: Optional[str] = None
    approval_triggers: Optional[dict] = None
    success_metrics: Optional[list] = None
    roadmap: Optional[list] = None


class ProjectOut(BaseModel):
    id: str
    title: str
    description: Optional[str]
    status: str
    autonomy_mode: str
    approval_triggers: dict
    goal: Optional[str]
    target_audience: Optional[str]
    monetization_model: Optional[str]
    success_metrics: list
    roadmap: list
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# TASKS
# ──────────────────────────────────────────────
class LivePlanStep(BaseModel):
    step: str
    status: str = "pending"  # pending | in_progress | done | skipped
    note: Optional[str] = None


class LivePlan(BaseModel):
    steps: List[LivePlanStep] = []
    notes: str = ""


class TaskCreate(BaseModel):
    project_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: Optional[str] = None
    priority: str = "medium"
    assigned_to: Optional[str] = None
    created_by: Optional[str] = "owner"
    requires_approval: bool = False
    tags: list = Field(default_factory=list)
    deadline: Optional[datetime] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None
    requires_approval: Optional[bool] = None
    live_plan: Optional[dict] = None
    tags: Optional[list] = None
    deadline: Optional[datetime] = None


class TaskOut(BaseModel):
    id: str
    project_id: Optional[str]
    parent_task_id: Optional[str]
    title: str
    description: Optional[str]
    status: str
    priority: str
    created_by: Optional[str]
    assigned_to: Optional[str]
    requires_approval: bool
    live_plan: dict
    tags: list
    deadline: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskCommentCreate(BaseModel):
    content: str
    author: str = "owner"
    attachments: list = Field(default_factory=list)


class TaskCommentOut(BaseModel):
    id: str
    task_id: str
    author: str
    content: str
    attachments: list
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# AGENTS
# ──────────────────────────────────────────────
class AgentOut(BaseModel):
    id: str
    name: str
    role: str
    status: str
    provider: Optional[str]
    model: Optional[str]
    tools: list
    config: dict
    current_task_id: Optional[str]
    tasks_completed: int

    class Config:
        from_attributes = True


class AgentUpdate(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    config: Optional[dict] = None
    status: Optional[str] = None


# ──────────────────────────────────────────────
# NOTIFICATIONS
# ──────────────────────────────────────────────
class NotificationOut(BaseModel):
    id: str
    type: str
    priority: str
    title: str
    body: Optional[str]
    task_id: Optional[str]
    project_id: Optional[str]
    is_read: bool
    vk_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────
class DashboardMetrics(BaseModel):
    requires_decision: List[NotificationOut]
    blockers: List[TaskOut]
    agents_status: List[AgentOut]
    active_projects: List[Any]
    today_metrics: dict
