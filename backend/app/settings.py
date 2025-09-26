from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/telegram_manager")
    api_id: int = int(os.getenv("API_ID", "0"))
    api_hash: str = os.getenv("API_HASH", "")
    sessions_dir: str = os.getenv("SESSIONS_DIR", "sessions")
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-please")
    default_access_password: str = os.getenv("DEFAULT_ACCESS_PASSWORD", "cbcelkfuftn24")


settings = Settings()

