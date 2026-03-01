import json
import os
from pydantic_settings import BaseSettings
from typing import Optional

def load_json_secrets() -> dict:
    # Path to secrets.json relative to this file (up two levels)
    # This works because config.py is in app/core/
    secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../secrets.json")
    if os.path.exists(secrets_path):
        try:
            with open(secrets_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

class Settings(BaseSettings):
    PROJECT_NAME: str = "OneTwenty SaaS"
    API_V1_STR: str = "/api/v1"
    
    # Database (to be filled from secrets.json or ENV)
    MONGO_URI: str = ""
    MONGO_DB: str = "OneTwenty_saas"
    SQLALCHEMY_DATABASE_URL: str = ""

    # Security
    SECRET_KEY: str = "unsecure_default_please_use_secrets_json"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 14400
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # AWS Settings for Bedrock & Transcribe
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-south-1"
    BEDROCK_MODEL_ID: str = "meta.llama3-8b-instruct-v1:0"
    AWS_S3_BUCKET: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Load secrets from JSON and pass as keyword arguments to overwrite defaults
settings = Settings(**load_json_secrets())