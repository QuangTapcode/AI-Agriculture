import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager

# Ép UTF-8 cho stdout/stderr trên Windows để tránh lỗi encode tiếng Việt
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware # type: ignore
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api import (
    ai, ai_chat, alert, assistant_library, auth, chat, crawler, crops, dashboard,
    harvest, locations, market, market_news, news, notifications, prices,
    price_forecast, pricing, public_contact, quality, reports, season, weather,
)
from app.api import admin as admin_router
from app.api import settings as settings_router
from app.core.config import settings
from app.core import database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        database.init_db()
        logger.info("Database initialized: %s", database.active_database_url)
    except Exception as exc:
        logger.warning("Database initialization warning: %s", exc)

    from app.tasks.alert_tasks import auto_alert_loop
    from app.tasks.crawler_tasks import auto_crawl_loop
    from app.tasks.real_data_refresh import real_data_refresh_loop
    interval = os.getenv("CRAWL_INTERVAL_SECONDS", "3600")
    crawl_task = asyncio.create_task(auto_crawl_loop())
    real_refresh_task = asyncio.create_task(real_data_refresh_loop())
    alert_task = asyncio.create_task(auto_alert_loop())
    logger.info("[Crawler] Started — seed 7 days on startup, update interval=%ss", interval)

    logger.info("[Alerts] Started scheduled evaluator")

    yield

    crawl_task.cancel()
    real_refresh_task.cancel()
    alert_task.cancel()
    try:
        await crawl_task
    except asyncio.CancelledError:
        pass
    try:
        await real_refresh_task
    except asyncio.CancelledError:
        pass
    try:
        await alert_task
    except asyncio.CancelledError:
        pass
    logger.info("[Crawler] Auto-crawl task stopped.")
    logger.info("[Alerts] Scheduled evaluator stopped.")

app = FastAPI(
    title="AgriAI Backend",
    description="API for harvest forecast, agricultural pricing, quality check, market suggestion and alerts.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(OperationalError)
@app.exception_handler(SQLAlchemyError)
async def db_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Database error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Cơ sở dữ liệu tạm thời không khả dụng. Vui lòng khởi động SQL Server và thử lại.",
            "error": "database_unavailable",
        },
    )

app.include_router(admin_router.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(ai.router)
app.include_router(ai_chat.router)
app.include_router(assistant_library.router)
app.include_router(crops.router)
app.include_router(harvest.router)
app.include_router(quality.router)
app.include_router(pricing.router)
app.include_router(prices.router)
app.include_router(price_forecast.router)
app.include_router(market.router)
app.include_router(alert.router)
app.include_router(weather.router)
app.include_router(crawler.router)
app.include_router(news.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)
app.include_router(reports.router)
app.include_router(season.router)
app.include_router(settings_router.router)
app.include_router(market_news.router)
app.include_router(locations.router)
app.include_router(public_contact.router)
app.include_router(alert.alerts_router)
app.include_router(alert.weather_alert_router)

os.makedirs(os.path.join(settings.UPLOAD_DIR, "quality_check"), exist_ok=True)


@app.get("/")
async def root():
    return {
        "message": "AgriAI API Server",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "ai_chat": "/api/ai-chat/message",
            "db_test": "/db-test",
            "crops_list": "/api/crops",
            "crop_detail": "/api/crops/{crop_id}",
            "crop_search": "/api/crops/search?keyword={keyword}",
            "harvest_forecast": "/api/harvest/forecast",
            "harvest_history": "/api/harvest/history/{user_id}",
            "harvest_schedules": "/api/harvest/schedules/{user_id}",
            "seasons": "/api/seasons",
            "season_summary": "/api/seasons/stats/summary",
            "quality_check": "/api/quality/check",
            "quality_grades": "/api/quality/grades",
            "quality_history": "/api/quality/history/{user_id}",
            "quality_detail": "/api/quality/{record_id}",
            "pricing_current": "/api/pricing/current?crop_name={crop_name}&region={region}",
            "pricing_suggest": "/api/pricing/suggest",
            "pricing_forecast_legacy": "/api/pricing/forecast",
            "pricing_history": "/api/pricing/history/{crop_name}/{region}",
            "pricing_compare_regions": "/api/pricing/compare-regions/{crop_name}",
            "price_forecast": "/api/price-forecast/predict",
            "market_channels": "/api/market/channels",
            "market_suggest": "/api/market/suggest",
            "market_history": "/api/market/history/{user_id}",
            "alert_create": "/api/alert/create",
            "alert_list": "/api/alert/list",
            "alert_detail": "/api/alert/{alert_id}",
            "alert_deactivate": "/api/alert/{alert_id}",
            "weather_current": "/api/weather/current/{region}",
            "crawler_latest_data": "/api/crawler/latest-crawled-data",
            "crawler_summary":     "/api/crawler/summary",
            "crawler_standard_price": "/api/crawler/standard-price?crop_name={crop_name}",
            "weather_create":      "/api/weather/",
            "price_qa":            "/api/chat/price-qa",
            "weather_price_forecast":  "/api/pricing/weather-forecast?crop_name={crop_name}&region={region}",
            "news_market_impact":      "/api/news/market-impact",
            "news_china_trade":        "/api/news/china-trade",
            "news_disasters":          "/api/news/disasters",
            "news_combined_factor":    "/api/news/combined-factor",
            "news_price_adjusted":     "/api/news/price-with-news",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.get("/db-test")
async def db_test():
    db = database.SessionLocal()
    try:
        result = db.execute(text("SELECT 1")).scalar()
        return {
            "status": "success",
            "message": "Database connection successful",
            # Không trả nguyên chuỗi kết nối: endpoint này không cần đăng nhập
            # và active_database_url chứa mật khẩu tài khoản sa.
            **database.thong_tin_ket_noi(),
            "result": result,
        }
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {exc}") from exc
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
