import os
from celery import Celery
from datetime import timedelta

from celery.schedules import crontab

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# include: worker phải import các module này thì decorator @celery_app.task
# mới chạy và task mới có mặt trong registry. Thiếu nó thì Beat vẫn phát
# lịch đều nhưng worker trả lời "Received unregistered task".
celery_app = Celery(
    "agri_tasks",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.tasks.crawler_tasks",
        "app.tasks.alert_tasks",
        "app.tasks.cleanup_tasks",
    ],
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Ho_Chi_Minh',
    enable_utc=True,
)

# Số phút giữa hai lần cào thời tiết. Open-Meteo phát quan trắc theo lưới 15
# phút nên cào thưa hơn là bỏ lỡ; 6 toạ độ x 6 lần/giờ = 864 lượt/ngày, còn
# xa hạn mức 10.000 lượt/ngày của gói miễn phí.
WEATHER_CRAWL_MINUTES = int(os.getenv("WEATHER_CRAWL_MINUTES", "10"))

# Bảng điều khiển chỉ đọc cache, nên nhịp cào quyết định độ tươi người dùng
# thấy. Đặt bằng CACHE_TTL_MINUTES tương ứng: giá 180 phút, tin tức 120 phút.
PRICE_CRAWL_MINUTES = int(os.getenv("PRICE_CRAWL_MINUTES", "180"))
NEWS_CRAWL_MINUTES = int(os.getenv("NEWS_CRAWL_MINUTES", "120"))

# Cấu hình Celery Beat (Lập lịch tự động)
celery_app.conf.beat_schedule = {
    # Thời tiết đứng riêng, không đi ké crawler giá: cào giá hỏng thì thời
    # tiết vẫn phải cập nhật.
    "crawl-weather-realtime": {
        "task": "app.tasks.crawler_tasks.crawl_weather_realtime",
        "schedule": timedelta(minutes=WEATHER_CRAWL_MINUTES),
    },
    # Trước đây chỉ chạy 2h sáng. Cache giá hết hạn sau 3 giờ nên suốt phần
    # còn lại của ngày mọi request đều gặp cache miss và tự đi cào.
    "crawl-prices": {
        "task": "app.tasks.crawler_tasks.run_price_crawler",
        "schedule": timedelta(minutes=PRICE_CRAWL_MINUTES),
    },
    # Giá chính thống (thitruongnongsan.gov.vn) đi đường riêng, không nằm
    # trong run_price_crawler vốn chỉ cào các trang bán lẻ.
    "refresh-official-prices": {
        "task": "app.tasks.crawler_tasks.refresh_official_prices",
        "schedule": timedelta(minutes=PRICE_CRAWL_MINUTES),
    },
    "crawl-market-news": {
        "task": "app.tasks.crawler_tasks.refresh_market_news",
        "schedule": timedelta(minutes=NEWS_CRAWL_MINUTES),
    },
    "check-price-alerts-hourly": {
        "task": "app.tasks.alert_tasks.check_active_alerts",
        "schedule": crontab(minute=0), # Chạy đầu mỗi giờ
    },
    "cleanup-uploads-weekly": {
        "task": "app.tasks.cleanup_tasks.cleanup_old_uploads",
        "schedule": crontab(day_of_week='sunday', hour=3, minute=0), # Chạy 3h sáng Chủ Nhật
    }
}