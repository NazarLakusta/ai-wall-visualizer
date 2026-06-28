from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_SECRETS = frozenset({
    "change-me",
    "change-me-in-production",
    "change-me-jwt",
    "change-me-jwt-secret",
})

_WEAK_PASSWORDS = frozenset({
    "admin123",
    "superadmin123",
    "password",
    "changeme",
    "change-me-before-production",
})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-me"
    jwt_secret: str = "change-me-jwt"
    jwt_expire_minutes: int = 60

    database_url: str = "postgresql+asyncpg://wallviz:wallviz@localhost:5432/wallviz"
    database_url_sync: str = "postgresql://wallviz:wallviz@localhost:5432/wallviz"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    telegram_bot_token: str = ""
    telegram_webhook_url: str = ""
    webapp_url: str = "http://localhost/app"
    internal_api_url: str = "http://api:8000"

    storage_path: str = "./storage"
    retention_hours: int = 36
    max_upload_mb: int = 20

    torch_num_threads: int = 2
    sam_checkpoint_path: str = "/app/models/mobile_sam.pt"
    max_image_size: int = 1024
    wall_confidence_threshold: float = 0.85
    segformer_model_id: str = "nvidia/segformer-b5-finetuned-ade-640-640"

    admin_email: str = "admin@example.com"
    admin_password: str = "admin123"
    platform_admin_email: str = "super@example.com"
    platform_admin_password: str = "superadmin123"
    default_store_name: str = "Demo Store"
    default_store_slug: str = "demo"

    cleanup_interval_minutes: int = 60

    # AI queue / launch capacity (tune per VPS)
    ai_worker_count: int = 1
    avg_processing_seconds: int = 45
    max_ai_queue: int = 80

    # Platform owner ops alerts (private Telegram bot → your chat)
    ops_telegram_bot_token: str = ""
    ops_telegram_chat_id: str = ""
    ops_heartbeat_interval_minutes: int = 15
    ops_queue_warn_threshold: int = 10
    ops_queue_critical_threshold: int = 30

    @property
    def ops_bot_enabled(self) -> bool:
        return bool(self.ops_telegram_bot_token.strip())

    @property
    def ops_alerts_enabled(self) -> bool:
        return bool(self.ops_telegram_bot_token.strip() and self.ops_telegram_chat_id.strip())

    @property
    def ops_enabled(self) -> bool:
        return self.ops_alerts_enabled

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @model_validator(mode="after")
    def _require_strong_secrets_in_production(self) -> "Settings":
        if self.app_env.lower() != "production":
            return self
        if self.secret_key in _WEAK_SECRETS or len(self.secret_key) < 32:
            raise ValueError("Set SECRET_KEY to a random 32+ character string in production")
        if self.jwt_secret in _WEAK_SECRETS or len(self.jwt_secret) < 32:
            raise ValueError("Set JWT_SECRET to a random 32+ character string in production")
        if self.admin_password in _WEAK_PASSWORDS:
            raise ValueError("Set a strong ADMIN_PASSWORD before production deploy")
        if self.platform_admin_password in _WEAK_PASSWORDS:
            raise ValueError("Set a strong PLATFORM_ADMIN_PASSWORD before production deploy")
        return self


settings = Settings()
