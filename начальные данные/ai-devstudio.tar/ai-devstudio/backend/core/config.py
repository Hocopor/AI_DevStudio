from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    environment: str = "production"
    domain: str = "ai-devstudio.mak-o.ru"
    secret_key: str

    # Auth
    admin_login: str
    admin_password_hash: str
    jwt_secret: str
    jwt_ttl_minutes: int = 60
    jwt_refresh_ttl_days: int = 30

    # Database
    database_url: str

    # Redis
    redis_url: str
    redis_password: str

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_root_user: str
    minio_root_password: str

    # AI Providers
    deepseek_api_key: str = ""
    google_ai_studio_key: str = ""

    # VK
    vk_api_token: str
    vk_owner_user_id: int
    vk_group_id: int

    # Celery
    celery_broker_url: str
    celery_result_backend: str

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
