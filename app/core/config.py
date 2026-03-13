from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "惠企通企业端 MVP"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/hqt"
    cors_allow_origins: str = "*"
    llm_provider: str = "glm"
    llm_api_key: str | None = None
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model: str = "glm-4-flash"
    llm_timeout_seconds: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
