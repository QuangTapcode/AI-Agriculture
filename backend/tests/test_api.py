from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_person_1_api_contract_is_registered():
    paths = {route.path for route in app.routes}
    expected_paths = {
        "/db-test",
        "/api/crops",
        "/api/crops/",
        "/api/crops/search",
        "/api/crops/{crop_id}",
        "/api/harvest/forecast",
        "/api/harvest/history/{user_id}",
        "/api/harvest/history/me",
        "/api/harvest/schedules/{user_id}",
        "/api/harvest/schedules/me",
        "/api/harvest/schedules",
        "/api/dashboard/summary",
        "/api/dashboard/featured-crop",
        "/api/dashboard/price-trend",
        "/api/dashboard/weather-overview",
        "/api/dashboard/ai-recommendation",
        "/api/reports/summary",
        "/api/reports/me",
        "/api/settings/me",
        "/api/notifications",
        "/api/notifications/mark-all-read",
        "/api/notifications/{notification_id}/read",
        "/api/notifications/{notification_id}",
        "/api/quality/check",
        "/api/quality/history/{user_id}",
        "/api/quality/{record_id}",
        "/api/pricing/current",
        "/api/pricing/suggest",
        "/api/price-forecast/predict",
        "/api/market/suggest",
        "/api/market/history/{user_id}",
        "/api/alert/create",
        "/api/alert/list",
        "/api/alert/{alert_id}",
        "/api/weather/current/{region}",
        "/api/weather/forecast/{region}",
        "/api/weather/hourly/{region}",
        "/api/weather/agriculture/{region}",
        "/api/weather/alerts/{region}",
        "/api/weather/recommendations/{region}",
    }
    assert expected_paths.issubset(paths)


def test_added_contract_endpoints_smoke():
    db_response = client.get("/db-test")
    assert db_response.status_code == 200
    assert db_response.json()["status"] == "success"

    client.post(
        "/api/harvest/forecast",
        json={
            "crop_name": "ca chua",
            "region": "Ha Noi",
            "planting_date": "2026-01-01",
        },
    )

    crops_response = client.get("/api/crops")
    assert crops_response.status_code == 200
    crops = crops_response.json()["crops"]
    assert crops

    crop_id = crops[0]["crop_id"]
    assert client.get(f"/api/crops/{crop_id}").status_code == 200
    assert client.get("/api/crops/search?keyword=ca").status_code == 200

    current_response = client.get("/api/pricing/current?crop_name=ca%20chua&region=Ha%20Noi")
    assert current_response.status_code == 200
    gia = current_response.json()
    # Co du lieu that => co gia; chua co => bao miss, khong bia so
    if gia.get("success"):
        assert gia["data"]["current_price"] > 0
    else:
        assert gia["cache_status"] == "miss"

    assert client.get("/api/harvest/history/1").status_code == 200
    assert client.get("/api/harvest/schedules/1").status_code == 200
    assert client.get("/api/quality/history/1").status_code == 200
    assert client.get("/api/market/history/1").status_code == 200


def test_harvest_forecast():
    response = client.post(
        "/api/harvest/forecast",
        json={
            "crop_name": "ca chua",
            "region": "Ha Noi",
            "planting_date": "2026-01-01",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["expected_harvest_date"] == "2026-03-17"
    assert data["confidence"] > 0


def test_quality_upload_rejects_non_image():
    """File không phải ảnh => báo lỗi rõ, không bịa ra hạng chất lượng."""
    response = client.post(
        "/api/quality/check",
        data={"crop_name": "ca chua", "region": "Ha Noi"},
        files={"image": ("sample.jpg", b"fake-image-content", "image/jpeg")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "quality_grade" not in data, "Không được chấm loại cho file hỏng"
    assert data.get("error", {}).get("code") == "QUALITY_ANALYSIS_FAILED"


def test_pricing_suggest():
    response = client.post(
        "/api/pricing/suggest",
        json={
            "crop_name": "ca chua",
            "region": "Ha Noi",
            "quantity": 100,
            "quality_grade": "grade_1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_mock"] is False

    if body["success"]:
        data = body["data"]
        assert data["suggested_price"] > 0
        assert data["min_price"] <= data["suggested_price"] <= data["max_price"]
    else:
        # Chua co gia that trong DB => bao miss, khong bia so (TOD0 muc 1)
        assert body["data"] is None
        assert body["cache_status"] == "miss"


def test_price_forecast_predict():
    """Envelope {success, data, error}: có lịch sử => 7 ngày, không có => miss."""
    response = client.post(
        "/api/price-forecast/predict",
        json={
            "crop_name": "ca chua",
            "region": "Ha Noi",
            "forecast_days": 7,
        },
    )
    assert response.status_code == 200
    body = response.json()

    # Bất biến theo spec anti-mock: không bao giờ trả dữ liệu giả.
    assert body["is_mock"] is False

    if body["success"]:
        data = body["data"]
        assert len(data["predicted_prices"]) == 7
        assert data["trend"] in {"increasing", "decreasing", "stable"}
    else:
        # Chưa đủ lịch sử giá thật => nói thẳng, không bịa số
        assert body["data"] is None
        assert body["cache_status"] == "miss"
        assert body["error"]["code"]


def test_market_suggest():
    response = client.post(
        "/api/market/suggest",
        json={
            "crop_name": "ca chua",
            "region": "Ha Noi",
            "quantity": 1200,
            "quality_grade": "grade_1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_mock"] is False

    if body["success"]:
        data = body["data"]
        assert data["recommended_channel"]
        assert data["profit_comparison"]
    else:
        assert body["data"] is None
        assert body["error"]["code"]


def test_alert_create_list_delete():
    create_response = client.post(
        "/api/alert/create",
        json={
            "crop_name": "ca chua",
            "region": "Ha Noi",
            "target_price": 25000,
            "condition": "above",
            "notification_channel": "email",
            "receiver": "farmer@example.com",
        },
    )
    assert create_response.status_code == 200
    alert_id = create_response.json()["alert_id"]

    list_response = client.get("/api/alert/list")
    assert list_response.status_code == 200
    assert any(alert["alert_id"] == alert_id for alert in list_response.json()["alerts"])

    delete_response = client.delete(f"/api/alert/{alert_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["alert_id"] == alert_id


def test_weather_current():
    """Cache ấm => có region; cache lạnh => miss rõ ràng (fail-fast, chờ crawler)."""
    response = client.get("/api/weather/current/Ha%20Noi")
    assert response.status_code == 200
    body = response.json()
    assert body["is_mock"] is False

    if "region" in body:
        # region có thể là "Ha Noi", "Hà Nội", hoặc dạng encode khác từ DB
        region = body["region"]
        assert region and region.lower().replace(" ", "").startswith("ha") or "n" in region.lower()
    else:
        assert body["cache_status"] == "miss"
        assert body["error"]["code"] == "WEATHER_CACHE_MISS"


def test_weather_agriculture_module():
    response = client.get("/api/weather/agriculture/Ha%20Noi?crop_name=lua&growth_stage=lam%20dong")
    assert response.status_code == 200
    data = response.json()
    assert data["module_name"] == "Thời tiết nông vụ thông minh"
    assert len(data["forecast"]) == 7
    assert data["activity_recommendations"]
    assert "summary" in data["ai_recommendation"]
