from typing import List, Union
from pydantic_settings import BaseSettings
from pydantic import Field, validator
import os


class Settings(BaseSettings):
    # アプリケーション設定
    APP_NAME: str = Field(default="AIMEE-Backend")
    APP_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")
    ENVIRONMENT: str = Field(default="development")
    
    # API設定
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    WORKERS: int = Field(default=1)
    API_V1_PREFIX: str = "/api/v1"
    
    # データベース設定
    DATABASE_URL: str = Field(...)
    DATABASE_POOL_SIZE: int = Field(default=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=40)
    
    # Redis設定
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_MAX_MEMORY: str = Field(default="512mb")
    REDIS_EVICTION_POLICY: str = Field(default="allkeys-lru")
    
    # AI/LLM設定（マルチモデル）
    OLLAMA_LIGHT_HOST: str = Field(default="ollama-light")
    OLLAMA_LIGHT_PORT: int = Field(default=11434)
    INTENT_MODEL: str = Field(default="qwen2:0.5b")
    
    OLLAMA_MAIN_HOST: str = Field(default="ollama-main")
    OLLAMA_MAIN_PORT: int = Field(default=11434)
    MAIN_MODEL: str = Field(default="gemma3:4b-instruct")
    
    # パフォーマンス最適化
    OLLAMA_NUM_PARALLEL: int = Field(default=4)
    OLLAMA_CONTEXT_SIZE: int = Field(default=2048)
    OLLAMA_BATCH_SIZE: int = Field(default=512)
    
    # ハイブリッド処理設定
    ENABLE_PARALLEL_PROCESSING: bool = Field(default=True)
    HYBRID_TIMEOUT_SECONDS: int = Field(default=10)
    STREAMING_RESPONSE: bool = Field(default=True)
    SIMPLE_TASK_THRESHOLD: float = Field(default=0.7)
    
    # ChromaDB設定
    CHROMADB_HOST: str = Field(default="chromadb")
    CHROMADB_PORT: int = Field(default=8000)
    CHROMADB_AUTH_TOKEN: str = Field(default="aimee-chroma-token")
    CHROMADB_COLLECTION: str = Field(default="aimee_knowledge")
    
    # RAG設定
    CHUNK_SIZE: int = Field(default=512)
    TOP_K_RESULTS: int = Field(default=5)
    SIMILARITY_THRESHOLD: float = Field(default=0.7)
    ENABLE_VECTOR_CACHE: bool = Field(default=True)
    CACHE_TTL_SECONDS: int = Field(default=3600)
    
    # セキュリティ設定
    SECRET_KEY: str = Field(...)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    
    # CORS設定
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000", "http://localhost:5173"])
    
    # OpenAI API（オプション）
    OPENAI_API_KEY: str = Field(default="")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v
    
    @validator("ENABLE_PARALLEL_PROCESSING", "STREAMING_RESPONSE", "ENABLE_VECTOR_CACHE", pre=True)
    def parse_bool(cls, v):
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes')
        return v


settings = Settings()