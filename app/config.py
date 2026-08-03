from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = ""
    webapp_url: str = "http://localhost:8000"
    reminder_times: str = "09:00,15:00,21:00"
    timezone: str = "Europe/Moscow"
    database_url: str = "sqlite+aiosqlite:///./fitness.db"
    admin_ids: str = ""

    @property
    def reminder_time_list(self) -> list[str]:
        return [t.strip() for t in self.reminder_times.split(",") if t.strip()]

    @property
    def admin_id_set(self) -> set[int]:
        if not self.admin_ids.strip():
            return set()
        return {int(x.strip()) for x in self.admin_ids.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Re-read .env (e.g. after changing WEBAPP_URL)."""
    get_settings.cache_clear()
    return get_settings()


def webapp_public_url() -> str:
    """Current Mini App URL from .env, always freshly loaded."""
    url = reload_settings().webapp_url.strip().rstrip("/")
    return url + "/"
