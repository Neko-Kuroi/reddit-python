# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    SESSION_COOKIE_NAME: str = "session"
    DEBUG: bool = False

    class Config:
        env_file = ".env"

# シングルトンとして使う
settings = Settings()
