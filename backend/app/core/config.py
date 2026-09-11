import json
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///./agri_ai.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "change-this-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    CLAUDE_API_KEY: str = ""
    # Mac dinh chay local qua Ollama: khong ton phi theo token, du lieu
    # nong dan khong roi khoi may chu, va chay duoc ca khi mat mang.
    AI_PROVIDER: str = "ollama"
    AI_API_KEY: str = ""
    AI_BASE_URL: str = "http://localhost:11434"
    AI_MODEL_NAME: str = "qwen3:4b-instruct"
    AI_TIMEOUT_SECONDS: float = 120.0
    AI_CONTEXT_TOKENS: int = 3072
    AI_MAX_OUTPUT_TOKENS: int = 256
    RAG_ENABLED: bool = True
    RAG_STORAGE_PATH: str = "storage/rag"
    RAG_EMBEDDING_MODEL: str = "embeddinggemma"
    RAG_TIMEOUT_SECONDS: float = 60.0
    RAG_TOP_K: int = 4
    RAG_MAX_CHUNKS_PER_DOCUMENT: int = 1
    RAG_MIN_SIMILARITY: float = 0.35
    KNOWLEDGE_AGENT_ENABLED: bool = False
    KNOWLEDGE_AGENT_HOUR: int = 2
    KNOWLEDGE_AGENT_MAX_DOCUMENTS: int = 20
    KNOWLEDGE_AGENT_MAX_BYTES: int = 52_428_800
    KNOWLEDGE_AGENT_MAX_TEXT_CHARS: int = 1_000_000
    KNOWLEDGE_AGENT_MIN_TEXT_CHARS: int = 800
    KNOWLEDGE_AGENT_QA_SIMILARITY: float = 0.22
    KNOWLEDGE_AGENT_SOURCES_FILE: str = ""
    KNOWLEDGE_AGENT_SOURCES_JSON: str = "[]"
    EXTERNAL_CONNECT_TIMEOUT_SECONDS: float = 3.0
    EXTERNAL_READ_TIMEOUT_SECONDS: float = 8.0
    EXTERNAL_WRITE_TIMEOUT_SECONDS: float = 10.0
    EXTERNAL_POOL_TIMEOUT_SECONDS: float = 5.0
    EXTERNAL_TOTAL_TIMEOUT_SECONDS: float = 12.0
    EXTERNAL_RETRY_COUNT: int = 1
    EXTERNAL_BACKOFF_SECONDS: float = 0.4

    WEATHER_API_KEY: str = ""
    WEATHER_PROVIDER: str = "open-meteo"
    WEATHER_API_BASE_URL: str = ""
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com"
    WEATHER_CACHE_TTL_SECONDS: int = 1800
    WEATHER_TIMEOUT_SECONDS: float = 10.0
    WEATHER_CONNECT_TIMEOUT_SECONDS: float = 4.0
    WEATHER_READ_TIMEOUT_SECONDS: float = 9.0
    WEATHER_RETRY_COUNT: int = 0
    REGION_COORDINATES_JSON: str = json.dumps(
        {
            "Ha Noi": {"latitude": 21.0285, "longitude": 105.8542},
            "Hà Nội": {"latitude": 21.0285, "longitude": 105.8542},
            "TP.HCM": {"latitude": 10.8231, "longitude": 106.6297},
            "Da Nang": {"latitude": 16.0544, "longitude": 108.2022},
            "Đà Nẵng": {"latitude": 16.0544, "longitude": 108.2022},
            "Can Tho": {"latitude": 10.0452, "longitude": 105.7469},
            "Cần Thơ": {"latitude": 10.0452, "longitude": 105.7469},
            "Lam Dong": {"latitude": 11.9404, "longitude": 108.4583},
            "Lâm Đồng": {"latitude": 11.9404, "longitude": 108.4583},
            "Hai Phong": {"latitude": 20.8449, "longitude": 106.6881},
            "Hải Phòng": {"latitude": 20.8449, "longitude": 106.6881},
        }
    )

    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""
    ZALO_OA_TOKEN: str = ""
    ZALO_OA_ID: str = ""
    ZALO_APP_ID: str = ""
    ZALO_APP_SECRET: str = ""
    ZALO_API_BASE_URL: str = "https://openapi.zalo.me"
    ESMS_API_KEY: str = ""
    ESMS_SECRET_KEY: str = ""
    ESMS_BRAND_NAME: str = "AgriAI"
    ESMS_SMS_TYPE: int = 2

    THITRUONG_NONGSAN_PRICE_URL: str = "https://thitruongnongsan.gov.vn/vn/nguonwmy.aspx"
    THITRUONG_NONGSAN_NEWS_URL: str = "https://thitruongnongsan.gov.vn/vn/xc0_tin-tuc.html"
    ENABLE_THITRUONG_NONGSAN_PRICE: bool = True
    ENABLE_THITRUONG_NONGSAN_NEWS: bool = True
    RETAIL_PRICE_SOURCES_JSON: str = json.dumps(
        [
            {"name": "BachHoaXanh", "url": "https://www.bachhoaxanh.com/"},
            {"name": "WinMart", "url": "https://winmart.vn/"},
            {"name": "GO", "url": "https://go-vietnam.vn/"},
            {"name": "Coopmart", "url": "https://cooponline.vn/"},
            {"name": "MMMegaMarket", "url": "https://online.mmvietnam.com/"},
        ]
    )

    PRICE_SOURCE_URLS_JSON: str = json.dumps(
        [
            {"name": "thitruongnongsan.gov.vn", "url": "https://thitruongnongsan.gov.vn/vn/nguonwmy.aspx"},
        ]
    )
    ENABLE_STOOQ_PRICE_SOURCE: bool = False
    MARKET_PRICE_API_URL: str = ""
    MARKET_PRICE_API_KEY: str = ""
    THITRUONGNONGSAN_BASE_URL: str = "https://thitruongnongsan.gov.vn"
    THITRUONGNONGSAN_ENABLED: bool = True
    APIFARMER_API_BASE_URL: str = ""
    APIFARMER_API_KEY: str = ""
    APIFARMER_ENABLED: bool = False
    APIFARMER_PRICE_ENDPOINT: str = "/prices/current"
    APIFARMER_HISTORY_ENDPOINT: str = ""
    APIFARMER_NEWS_ENDPOINT: str = "/news"
    TWELVEDATA_API_BASE_URL: str = "https://api.twelvedata.com"
    TWELVEDATA_API_KEY: str = ""
    TWELVEDATA_ENABLED: bool = False
    TWELVEDATA_PRICE_ENDPOINT: str = "/price"
    TWELVEDATA_TIME_SERIES_ENDPOINT: str = "/time_series"
    TWELVEDATA_NEWS_ENDPOINT: str = ""
    ENABLE_REALTIME_PRICE: bool = True
    ENABLE_MARKET_NEWS: bool = True
    PRICE_CACHE_TTL_MINUTES: int = 60
    NEWS_CACHE_TTL_MINUTES: int = 120
    ALLOW_MOCK_DATA: bool = True
    ALLOW_SAMPLE_DATA: bool = True
    USE_REALTIME_ONLY: bool = False
    EXCHANGE_RATE_API_URL: str = "https://open.er-api.com/v6/latest/USD"
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com"
    MARKET_API_BASE_URL: str = ""
    PRICE_SAVE_RATIO_WARN_THRESHOLD: float = 0.5

    # --- Firecrawl ---
    FIRECRAWL_API_KEY: str = ""
    FIRECRAWL_ENABLED: bool = False
    FIRECRAWL_BASE_URL: str = "https://api.firecrawl.dev"
    FIRECRAWL_RAW_STORAGE_PATH: str = "storage/raw_crawl"

    # --- Tavily ---
    TAVILY_API_KEY: str = ""
    TAVILY_ENABLED: bool = True
    TAVILY_SEARCH_DEPTH: str = "advanced"
    TAVILY_MAX_RESULTS: int = 10
    TAVILY_NEWS_CACHE_TTL_MINUTES: int = 120

    GOOGLE_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    USD_VND_FALLBACK_RATE: float = 26000.0
    MARKET_NEWS_RSS_URLS_JSON: str = json.dumps(
        [
            "https://vnexpress.net/rss/nong-nghiep.rss",
            "https://vnexpress.net/rss/kinh-doanh.rss",
        ]
    )
    MARKET_NEWS_CACHE_TTL_SECONDS: int = 1800

    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://172.17.176.1:5173",
        "http://172.17.176.1:5174",
        "http://172.17.176.1:5175",
    ]

    ENVIRONMENT: str = "development"
    UPLOAD_DIR: str = "storage/uploads"

    YOLO_MODEL_PATH: str = "ai_models/weights/best.pt"
    PRICE_MODEL_PATH: str = "ai_models/price_forecast/saved_models"
    HARVEST_MODEL_PATH: str = "ai_models/harvest_forecast/saved_models"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_secret(self):
        unsafe_keys = {"", "change-this-secret-key", "your-secret-key-change-this-in-production"}
        if self.ENVIRONMENT.lower() == "production" and self.SECRET_KEY in unsafe_keys:
            raise ValueError("SECRET_KEY must be set to a strong value in production")
        return self


settings = Settings()
