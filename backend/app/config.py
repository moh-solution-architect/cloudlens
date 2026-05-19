from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CloudLens"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # Feature flags
    use_mock_data: bool = True
    mock_data_seed: int = 42

    # AWS
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_default_region: str = "us-east-1"
    aws_account_id: str = "123456789012"

    # Azure
    azure_subscription_id: str = ""
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""

    # GCP
    gcp_project_id: str = ""
    gcp_billing_account_id: str = ""
    google_application_credentials: str = ""

    # Recommendation thresholds
    idle_cpu_threshold_percent: float = 5.0
    idle_lookback_days: int = 7
    rds_cpu_threshold_percent: float = 20.0
    rds_connections_threshold: int = 5

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
