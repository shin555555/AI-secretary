from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LINE
    line_channel_secret: str = ""
    line_channel_access_token: str = ""
    line_user_id: str = ""

    # Google
    google_credentials_path: str = "data/google_credentials.json"
    google_token_path: str = "data/google_token.json"

    # Gemini（フォールバック用）
    gemini_api_key: str = ""

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma2:9b-instruct-q5_K_M"

    # APScheduler
    briefing_hour: int = 8
    briefing_minute: int = 0

    # アプリ設定
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
