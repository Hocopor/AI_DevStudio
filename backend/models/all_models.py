import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, Text, Boolean, Integer, DateTime,
    ForeignKey, ARRAY, Numeric
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return str(uuid.uuid4())


# ──────────────────────────────────────────────
# PROJECTS
# ──────────────────────────────────────────────
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="active")
    # active | paused | done | archived
    autonomy_mode: Mapped[str] = mapped_column(String(50), default="stage_approval")
    # free | stage_approval | strict
    approval_triggers: Mapped[dict] = mapped_column(JSONB, default=dict)
    goal: Mapped[Optional[str]] = mapped_column(Text)
    target_audience: Mapped[Optional[str]] = mapped_column(Text)
    monetization_model: Mapped[Optional[str]] = mapped_column(Text)
    success_metrics: Mapped[list] = mapped_column(JSONB, default=list)
    roadmap: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="project", cascade="all, delete-orphan")


# ──────────────────────────────────────────────
# TASKS
# ──────────────────────────────────────────────
class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("projects.id", ondelete="CASCADE"))
    parent_task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="backlog")
    # backlog | todo | in_progress | review | awaiting_approval | testing | done | archived
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    # low | medium | high | critical
    created_by: Mapped[Optional[str]] = mapped_column(String(100))   # agent_id или 'owner'
    assigned_to: Mapped[Optional[str]] = mapped_column(String(100))  # agent_id
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    live_plan: Mapped[dict] = mapped_column(JSONB, default=lambda: {"steps": [], "notes": ""})
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Optional["Project"]] = relationship("Project", back_populates="tasks")
    comments: Mapped[list["TaskComment"]] = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
    subtasks: Mapped[list["Task"]] = relationship("Task", foreign_keys=[parent_task_id])


class TaskComment(Base):
    __tablename__ = "task_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"))
    author: Mapped[str] = mapped_column(String(100), nullable=False)  # agent_id или 'owner'
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    task: Mapped["Task"] = relationship("Task", back_populates="comments")


class AgentTaskMemory(Base):
    __tablename__ = "agent_task_memory"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id", ondelete="CASCADE"))
    project_id: Mapped[Optional[str]] = mapped_column(String(36))
    summary: Mapped[str] = mapped_column(Text, default="")
    key_points: Mapped[list] = mapped_column(JSONB, default=list)
    last_owner_reply: Mapped[Optional[str]] = mapped_column(Text)
    last_agent_question: Mapped[Optional[str]] = mapped_column(Text)
    raw_context_chars: Mapped[int] = mapped_column(Integer, default=0)
    compressed_context_chars: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ──────────────────────────────────────────────
# AGENTS
# ──────────────────────────────────────────────
class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)  # 'director', 'backend_dev', etc.
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="idle")
    # idle | active | error | disabled
    provider: Mapped[Optional[str]] = mapped_column(String(50))    # 'deepseek' | 'codex' | 'google'
    model: Mapped[Optional[str]] = mapped_column(String(100))
    system_prompt: Mapped[Optional[str]] = mapped_column(Text)
    tools: Mapped[list] = mapped_column(JSONB, default=list)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    current_task_id: Mapped[Optional[str]] = mapped_column(String(36))
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    skills: Mapped[list["AgentSkill"]] = relationship("AgentSkill", back_populates="agent")


class AgentSkill(Base):
    __tablename__ = "agent_skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    agent_id: Mapped[str] = mapped_column(String(50), ForeignKey("agents.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # промпт / инструкция
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    agent: Mapped["Agent"] = relationship("Agent", back_populates="skills")


# ──────────────────────────────────────────────
# AI PROVIDERS
# ──────────────────────────────────────────────
class AIProvider(Base):
    __tablename__ = "ai_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)   # 'deepseek' | 'codex' | 'google'
    display_name: Mapped[str] = mapped_column(String(100))
    provider_type: Mapped[str] = mapped_column(String(50))           # 'api_key' | 'oauth'
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)   # зашифрован
    config: Mapped[dict] = mapped_column(JSONB, default=dict)        # лимиты, настройки
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(50), default="unknown")  # ok | limit | error
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CodexAccount(Base):
    __tablename__ = "codex_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    label: Mapped[str] = mapped_column(String(100))            # 'account-1', 'account-2', ...
    oauth_token_encrypted: Mapped[str] = mapped_column(Text)   # зашифрован
    priority: Mapped[int] = mapped_column(Integer, default=1)  # порядок в очереди
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    limit_info: Mapped[dict] = mapped_column(JSONB, default=dict)  # лимиты из API
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ──────────────────────────────────────────────
# API USAGE LOGS
# ──────────────────────────────────────────────
class APIUsageLog(Base):
    __tablename__ = "api_usage_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    agent_id: Mapped[Optional[str]] = mapped_column(String(50))
    provider: Mapped[Optional[str]] = mapped_column(String(50))
    model: Mapped[Optional[str]] = mapped_column(String(100))
    tokens_input: Mapped[int] = mapped_column(Integer, default=0)
    tokens_output: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0)
    task_id: Mapped[Optional[str]] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ──────────────────────────────────────────────
# NOTIFICATIONS
# ──────────────────────────────────────────────
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    # requires_decision | blocker | stage_complete | financial | system_error | provider_limit | digest
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    # critical | high | medium | info
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text)
    task_id: Mapped[Optional[str]] = mapped_column(String(36))
    project_id: Mapped[Optional[str]] = mapped_column(String(36))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    vk_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ──────────────────────────────────────────────
# SYSTEM LOGS
# ──────────────────────────────────────────────
class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    level: Mapped[str] = mapped_column(String(20), default="info")  # debug | info | warning | error
    source: Mapped[Optional[str]] = mapped_column(String(100))      # agent_id | 'system' | 'api'
    message: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
