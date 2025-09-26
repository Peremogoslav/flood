from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/telegram_manager"
    api_id: int = 0
    api_hash: str = ""
    sessions_dir: str = "sessions"


settings = Settings()

