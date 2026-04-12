from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from core.config import settings
from core.database import engine
from models.all_models import Base
from api.routes import auth, projects, tasks, agents, notifications, dashboard
from api.websocket import ws_dashboard, ws_project
from services.minio_service import init_buckets


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Инициализация при старте"""
    logger.info("🚀 AI DevStudio запускается...")

    # Создать таблицы БД (если не существуют)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✅ БД готова")

    # Инициализировать MinIO бакеты
    await init_buckets()
    logger.info("✅ MinIO готов")

    yield

    logger.info("🛑 AI DevStudio останавливается...")


app = FastAPI(
    title="AI DevStudio API",
    version="1.0.0",
    docs_url="/api/docs" if settings.environment == "development" else None,
    redoc_url=None,
    lifespan=lifespan,
)

# CORS — только свой домен
app.add_middleware(
    CORSMiddleware,
    allow_origins=[f"https://{settings.domain}", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Роуты
app.include_router(auth.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(tasks.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")

# WebSocket
from fastapi import WebSocket
@app.websocket("/ws/dashboard")
async def websocket_dashboard(websocket: WebSocket):
    await ws_dashboard(websocket)

@app.websocket("/ws/project/{project_id}")
async def websocket_project(websocket: WebSocket, project_id: str):
    await ws_project(websocket, project_id)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "AI DevStudio"}
