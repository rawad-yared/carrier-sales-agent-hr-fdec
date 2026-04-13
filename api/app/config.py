from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = Field(..., alias="API_KEY")
    database_url: str = Field(..., alias="DATABASE_URL")
    fmcsa_webkey: str = Field("", alias="FMCSA_WEBKEY")

    floor_pct: float = Field(0.92, alias="FLOOR_PCT")
    target_pct: float = Field(0.98, alias="TARGET_PCT")
    strategy: str = Field("smart", alias="STRATEGY")

    rate_limit_per_min: int = Field(60, alias="RATE_LIMIT_PER_MIN")

    loads_json_path: str = Field("/app/data/loads.json", alias="LOADS_JSON_PATH")


@lru_cache
def get_settings() -> Settings:
    return Settings()
