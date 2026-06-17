from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BMX Track Control Cloud"
    database_url: str = "sqlite:///./bmx_control.db"
    upload_check_interval_minutes: int = 5
    default_photo_interval_minutes: int = 120
    enable_scheduler: bool = True
    local_upload_dir: str = "app/uploads"
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    cloudinary_upload_preset: str | None = None
    session_secret_key: str = "change-this-secret-key"
    admin_username: str = "admin"
    admin_password: str = "admin123"
    jimmy_username: str | None = "Jimmy"
    jimmy_password: str | None = "207720"
    jimmy_role: str = "supervisor"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

