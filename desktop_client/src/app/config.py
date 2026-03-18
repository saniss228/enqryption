from __future__ import annotations

from pathlib import Path

from appdirs import user_data_dir
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DATA_DIR = Path(user_data_dir("SecureMessengerClient", "encriptyon"))


class ClientSettings(BaseSettings):
    api_base_url: str = Field("http://127.0.0.1:8000")
    data_dir: Path = Field(DEFAULT_DATA_DIR)
    encryption_salt: str = Field("replace-with-a-long-random-salt", repr=False)
    media_dir: Path = Field(DEFAULT_DATA_DIR / "media")
    token_file: Path = Field(DEFAULT_DATA_DIR / "auth.token")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = ClientSettings()
settings.media_dir = settings.data_dir / "media"
settings.token_file = settings.data_dir / "auth.token"
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.media_dir.mkdir(parents=True, exist_ok=True)
