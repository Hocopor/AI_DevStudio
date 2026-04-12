import io
from minio import Minio
from minio.error import S3Error
from loguru import logger
from core.config import settings


BUCKETS = ["projects", "agents", "products", "backups"]

_client: Minio = None


def get_minio() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_root_user,
            secret_key=settings.minio_root_password,
            secure=False,  # внутри Docker-сети HTTP
        )
    return _client


async def init_buckets():
    """Создать бакеты при старте приложения"""
    client = get_minio()
    for bucket in BUCKETS:
        try:
            if not client.bucket_exists(bucket):
                client.make_bucket(bucket)
                logger.info(f"MinIO: создан бакет '{bucket}'")
        except S3Error as e:
            logger.error(f"MinIO: ошибка создания бакета '{bucket}': {e}")


def upload_file(
    bucket: str,
    object_path: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """Загрузить файл в MinIO. Возвращает путь объекта."""
    client = get_minio()
    client.put_object(
        bucket_name=bucket,
        object_name=object_path,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_path


def download_file(bucket: str, object_path: str) -> bytes:
    """Скачать файл из MinIO"""
    client = get_minio()
    response = client.get_object(bucket, object_path)
    return response.read()


def delete_file(bucket: str, object_path: str):
    client = get_minio()
    client.remove_object(bucket, object_path)


def list_files(bucket: str, prefix: str = "") -> list[str]:
    client = get_minio()
    objects = client.list_objects(bucket, prefix=prefix, recursive=True)
    return [obj.object_name for obj in objects]


def save_agent_artifact(
    project_id: str,
    agent_id: str,
    filename: str,
    data: bytes,
    content_type: str = "text/plain",
) -> str:
    path = f"{project_id}/{agent_id}/{filename}"
    return upload_file("projects", path, data, content_type)
