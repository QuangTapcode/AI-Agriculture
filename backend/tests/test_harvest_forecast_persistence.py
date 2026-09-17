from datetime import date

from app.core.database import SessionLocal
from app.models.harvest import HarvestForecast, HarvestSchedule
from app.schemas.harvest_schema import HarvestForecastRequest
from app.services.harvest_service import harvest_service


def test_forecast_harvest_does_not_create_a_season_or_forecast_row(monkeypatch):
    monkeypatch.setattr(harvest_service, "_get_predictor", lambda: None)
    monkeypatch.setattr(harvest_service, "_thoi_tiet_cho_du_bao", lambda db, region: None)
    monkeypatch.setattr(harvest_service, "_weather_risk_label", lambda db, region: "low")
    monkeypatch.setattr(harvest_service, "_market_condition", lambda db, crop_name, region: "neutral")

    db = SessionLocal()
    try:
        schedules_before = db.query(HarvestSchedule).count()
        forecasts_before = db.query(HarvestForecast).count()

        result = harvest_service.forecast_harvest(
            db,
            HarvestForecastRequest(
                crop_name="ca chua",
                region="Ha Noi",
                planting_date=date(2026, 1, 1),
            ),
        )

        assert result["expected_harvest_date"] == date(2026, 3, 17)
        assert db.query(HarvestSchedule).count() == schedules_before
        assert db.query(HarvestForecast).count() == forecasts_before
    finally:
        db.close()
