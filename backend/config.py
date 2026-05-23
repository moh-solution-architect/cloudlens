"""
CloudLens — centralised configuration via environment variables.
All secrets are read from env vars — never hardcoded.
"""
from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name:    str  = "CloudLens"
    app_version: str  = "1.0.0"
    debug:       bool = False
    use_mock_data: bool = True   # Set False for real cloud credentials

    # AWS
    aws_access_key_id:     str = ""
    aws_secret_access_key: str = ""
    aws_region:            str = "us-east-1"
    aws_account_id:        str = "123456789012"

    # Azure
    azure_subscription_id: str = ""
    azure_tenant_id:       str = ""
    azure_client_id:       str = ""
    azure_client_secret:   str = ""

    # GCP
    gcp_project_id:              str = ""
    gcp_service_account_key_path: str = ""

    # Cost analysis
    lookback_days:            int   = 30
    idle_cpu_threshold:       float = 5.0   # %
    idle_observation_days:    int   = 7
    rightsize_cpu_threshold:  float = 20.0  # %

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
