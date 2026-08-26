"""Application settings.

Every setting has a default so the stack boots on a clean clone with no .env.
A value may have a default only if it is not a secret; this phase has none.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app_password@db:5432/app_db"
    log_level: str = "INFO"
    seed_anchor_date: str = ""
    frontend_origin: str = "http://localhost:5173"


settings = Settings()
