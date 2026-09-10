from datetime import date, datetime, timedelta
from typing import Dict, Optional
from unicodedata import category, normalize

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.harvest_repository import (
    create_harvest_forecast,
    get_harvest_forecast_history,
    get_harvest_schedules_by_user,
)
from app.repositories.common import ensure_crop
from app.schemas.harvest_schema import HarvestForecastRequest, HarvestScheduleCreateRequest


class HarvestService:
    # Thời gian sinh trưởng (ngày) từ khi trồng cây giống đến thu hoạch đầu tiên.
    # Cây lâu năm (sầu riêng, xoài, cà phê...) tính theo năm trồng mới.
    # Cây ngắn ngày tính theo vụ.
    default_growth_days = {
        # ── Rau màu ngắn ngày ──────────────────────────────
        "ca chua":    75,   # Cà chua: 70-80 ngày
        "dua chuot":  60,   # Dưa chuột: 55-65 ngày
        "rau muong":  30,   # Rau muống: 25-35 ngày
        "cai xanh":   45,   # Cải xanh: 40-50 ngày
        "ot":         90,   # Ớt: 85-100 ngày
        "dua hau":    80,   # Dưa hấu: 70-90 ngày
        "khoai lang": 100,  # Khoai lang: 90-110 ngày
        "khoai tay":  90,   # Khoai tây: 80-100 ngày
        "hanh":       60,   # Hành tây: 55-70 ngày
        "toi":        90,   # Tỏi: 80-100 ngày
        "bap cai":    70,   # Bắp cải: 60-80 ngày
        "xup lo":     70,   # Súp lơ/Bông cải: 60-80 ngày
        # ── Ngũ cốc ────────────────────────────────────────
        "lua":       105,   # Lúa: 90-120 ngày (tùy giống)
        "ngo":        90,   # Ngô: 80-100 ngày
        "dau tuong":  95,   # Đậu tương: 85-110 ngày
        "dau phong": 120,   # Đậu phộng/Lạc: 110-130 ngày
        # ── Cây ăn quả lâu năm ────────────────────────────
        # (tính từ khi trồng cây giống ghép đến thu hoạch vụ đầu tiên)
        "sau rieng": 1460,  # Sầu riêng: 4-6 năm (cây giống ghép); từ ra hoa đến quả: 90-120 ngày
        "xoai":      1095,  # Xoài: 3-4 năm từ cây giống ghép
        "mit":       1460,  # Mít: 4-5 năm từ cây giống
        "bo":        1825,  # Bơ: 5-7 năm từ cây giống (giống ghép ~3 năm)
        "vai":        730,  # Vải: 2-3 năm từ cây giống ghép
        "nhan":       730,  # Nhãn: 2-3 năm từ cây giống ghép
        "chom chom":  730,  # Chôm chôm: 2-3 năm từ cây giống ghép
        "buoi":      1095,  # Bưởi: 3-4 năm từ cây giống ghép
        "cam":        730,  # Cam: 2-3 năm từ cây giống ghép
        "quyt":       730,  # Quýt: 2-3 năm từ cây giống ghép
        "chanh":      548,  # Chanh: 1.5-2 năm từ cây giống ghép
        "chuoi":      365,  # Chuối: 10-12 tháng từ khi trồng chồi
        "du du":      270,  # Đu đủ: 8-10 tháng từ hạt
        "dua":        365,  # Dứa/Khóm: 12-18 tháng từ chồi
        "thanh long":  540, # Thanh long: 18 tháng từ hom giống đến thu hoạch đầu tiên
        "mang cut":  1825,  # Măng cụt: 5-6 năm từ hạt (cây thực sinh)
        "sapoche":   1460,  # Sapôchê/Hồng xiêm: 4-5 năm từ cây giống
        "na":         548,  # Na/Mãng cầu: 1.5-2 năm từ cây giống
        # ── Cây công nghiệp ────────────────────────────────
        "ca phe":    1095,  # Cà phê: 3-4 năm từ cây giống
        "ho tieu":   1095,  # Hồ tiêu: 3-4 năm từ hom giống
        "cao su":    2555,  # Cao su: 7 năm từ khi trồng đến khai thác
        "dieu":      1460,  # Điều: 4-5 năm từ cây giống
        "mia":        365,  # Mía: 10-12 tháng từ hom giống
        "san":        270,  # Sắn/Mì: 8-12 tháng tùy giống
        "che":       1095,  # Chè (trà): 3-4 năm từ cây giống đến thu búp đầu tiên
    }

    @staticmethod
    def _realtime_only() -> bool:
        return bool(settings.USE_REALTIME_ONLY) and not bool(settings.ALLOW_MOCK_DATA or settings.ALLOW_SAMPLE_DATA)

    # Mô tả giai đoạn sinh trưởng cho các loại cây phổ biến
    _growth_stages = {
        "sau rieng": [
            "Tháng 1-6: Cây giống, làm đất, trồng mới",
            "Năm 1-2: Nuôi cây, bón phân, cắt tỉa tạo tán",
            "Năm 2-3: Cây bắt đầu phân cành cấp 1, cấp 2",
            "Năm 3-4: Cây trưởng thành, có thể ra hoa vụ đầu",
            "Từ ra hoa → quả chín: 90-120 ngày (3-4 tháng)",
            "Thu hoạch: khi quả có mùi thơm, gai mềm, đường rãnh nở",
        ],
        "ca phe": [
            "Tháng 1-6: Ươm hạt, cây giống trong vườn ươm",
            "Năm 1-2: Trồng mới, bón phân, làm giàn che",
            "Năm 2-3: Cây phát triển bộ khung, tỉa cành",
            "Năm 3-4: Ra hoa lần đầu (hoa trắng thơm), đậu quả",
            "Thu hoạch: khi quả chín đỏ/vàng (9-11 tháng sau ra hoa)",
        ],
        "lua": [
            "Ngày 1-7: Ngâm ủ, gieo mạ hoặc sạ thẳng",
            "Ngày 7-25: Giai đoạn mạ / cây con",
            "Ngày 25-60: Đẻ nhánh, làm đòng",
            "Ngày 60-80: Trổ bông, phơi màu",
            "Ngày 80-105: Chín sữa → chín hoàn toàn",
        ],
        "thanh long": [
            "Tháng 1-3: Trồng hom, bám giàn",
            "Tháng 3-12: Nuôi cành, phát triển thân leo",
            "Tháng 12-18: Ra hoa lần đầu",
            "Từ ra hoa → thu hoạch: 28-35 ngày",
            "Cho trái quanh năm sau khi trưởng thành",
        ],
    }

    @staticmethod
    def _get_predictor():
        try:
            from ai_models.harvest_forecast.predictor import harvest_predictor

            return harvest_predictor
        except ImportError:
            return None

    def _thoi_tiet_cho_du_bao(self, db: Session, region: str) -> dict | None:
        """Thời tiết trung bình 7 ngày tới, để predictor điều chỉnh ngày thu hoạch.

        Một ngày nắng 39°C không nói lên điều gì; lấy trung bình cả tuần mới
        phản ánh được xu hướng. Không có dữ liệu thì trả None để predictor hạ
        độ tin cậy thay vì đoán bừa.
        """
        if db is None:
            return None
        try:
            from app.services.weather_service import weather_service

            du_bao = weather_service.get_weather_forecast(db, region, 7, chi_doc_cache=True)
        except Exception:
            return None

        ngay = [d for d in (du_bao or []) if isinstance(d, dict)]
        if not ngay:
            return None

        def tb(khoa, mac_dinh=None):
            gia_tri = [float(d[khoa]) for d in ngay if d.get(khoa) is not None]
            return round(sum(gia_tri) / len(gia_tri), 1) if gia_tri else mac_dinh

        return {
            "temperature": tb("temp_max"),
            "rainfall": tb("rainfall"),
            "humidity": tb("humidity"),
            "so_ngay": len(ngay),
        }

    def forecast_harvest(
        self,
        db: Session,
        request: HarvestForecastRequest,
        user_id: int | None = None,
    ) -> dict:
        crop_name = request.crop_name
        region = request.region
        planting_date = request.planting_date

        growth_duration = self._resolve_growth_days(db, crop_name)
        # Trước đây dòng này gán cứng None và không bao giờ được gán lại, nên
        # toàn bộ phần điều chỉnh theo thời tiết trong HarvestPredictor là code
        # chết và kết quả chỉ còn là ngày trồng + số ngày tra bảng.
        weather_for_predictor = self._thoi_tiet_cho_du_bao(db, region)
        so_ngay_thoi_tiet = (weather_for_predictor or {}).get("so_ngay", 0)

        predictor = self._get_predictor()
        if predictor:
            try:
                ai_result = predictor.predict(
                    crop_name=crop_name,
                    planting_date=datetime.combine(planting_date, datetime.min.time()),
                    region=region,
                    growth_duration_days=growth_duration,
                    weather_data=weather_for_predictor,
                )
                growth_days = ai_result.get("growth_days", self._growth_days_for(crop_name))
                expected_date = planting_date + timedelta(days=growth_days)
                warning = ai_result.get("warning") or self._warning_for(expected_date)
                recommendation = ai_result.get(
                    "recommendation",
                    f"Dự kiến thu hoạch sau {growth_days} ngày. Nên theo dõi thời tiết trước thu hoạch.",
                )
                confidence = ai_result.get("confidence", 0.78)
            except Exception:
                predictor = None

        if not predictor:
            if self._realtime_only():
                return {
                    "_api_error": True,
                    "error_code": "REALTIME_API_FAILED",
                    "error_message": "Không thể tải dự báo thu hoạch realtime. Vui lòng thử lại sau.",
                    "source": "realtime_api",
                }
            growth_days = self._growth_days_for(crop_name)
            expected_date = planting_date + timedelta(days=growth_days)
            warning = self._warning_for(expected_date)
            years = growth_days // 365
            months = (growth_days % 365) // 30
            if years > 0:
                duration_str = f"{years} năm {months} tháng" if months else f"{years} năm"
            else:
                duration_str = f"{growth_days} ngày"
            recommendation = (
                f"Dự kiến thu hoạch {crop_name} tại {region} vào {expected_date.strftime('%d/%m/%Y')} "
                f"(sau {duration_str} kể từ ngày trồng). "
                "Chuẩn bị nhân lực và thiết bị trước 1-2 tuần. "
                "Theo dõi thời tiết thường xuyên để điều chỉnh kế hoạch."
            )
            confidence = 0.78

        growth_stages = self._get_growth_stages(crop_name)
        earliest_date = expected_date - timedelta(days=max(3, int(growth_days * 0.06)))
        latest_date = expected_date + timedelta(days=max(3, int(growth_days * 0.08)))
        weather_risk = self._weather_risk_label(db, region)
        market_condition = self._market_condition(db, crop_name, region)
        preparation_tasks = self._preparation_tasks(crop_name, expected_date)
        record = create_harvest_forecast(
            db,
            crop_name=crop_name,
            region=region,
            planting_date=planting_date,
            expected_harvest_date=expected_date,
            confidence=confidence,
            warning=warning,
            recommendation=recommendation,
            user_id=user_id,
        )

        return {
            "crop_name": crop_name,
            "crop": crop_name,
            "region": region,
            # Nói rõ dự báo dựa trên bao nhiêu ngày thời tiết thật; 0 nghĩa là
            # chỉ tra bảng sinh trưởng, không có điều chỉnh nào.
            "weather_days_used": so_ngay_thoi_tiet,
            "planting_date": planting_date,
            "expected_harvest_date": expected_date,
            "earliest_harvest_date": earliest_date,
            "optimal_harvest_date": expected_date,
            "latest_harvest_date": latest_date,
            "growth_days": growth_days if not predictor else self._growth_days_for(crop_name),
            "weather_risk": weather_risk,
            "market_condition": market_condition,
            "confidence": confidence,
            "warning": warning,
            "recommendation": recommendation,
            "preparation_tasks": preparation_tasks,
            "growth_stages": growth_stages,
            "source": "ai_generated" if predictor else "mock",
            "source_name": "Harvest optimizer AI/rule engine",
            "is_mock": not bool(predictor),
            "cache_status": "computed",
            "created_at": getattr(record, "created_at", None),
        }

    def predict_harvest_date(
        self,
        db: Session,
        crop_name: str,
        planting_date: datetime,
        region: str,
        user_id: int | None = None,
    ) -> dict:
        planting_day = planting_date.date() if hasattr(planting_date, "date") else planting_date
        request = HarvestForecastRequest(
            crop_name=crop_name,
            region=region,
            planting_date=planting_day,
        )
        result = self.forecast_harvest(db, request, user_id=user_id)
        if result.get("_api_error"):
            return result
        return {
            **result,
            "predicted_harvest_date": result["expected_harvest_date"],
            "growth_days": self._growth_days_for(crop_name),
            "recommendations": [result["recommendation"]],
        }

    def create_harvest_schedule(
        self,
        db: Session,
        user_id: int,
        crop_id: int,
        region: str,
        planting_date: date,
        expected_harvest_date: date,
        area_size: Optional[float] = None,
        estimated_yield_kg: Optional[float] = None,
        notes: Optional[str] = None,
    ):
        try:
            from app.models.harvest import HarvestSchedule

            schedule = HarvestSchedule(
                UserID=user_id,
                CropID=crop_id,
                Region=region,
                PlantingDate=planting_date,
                ExpectedHarvestDate=expected_harvest_date,
                AreaSize=area_size,
                EstimatedYieldKg=estimated_yield_kg,
                Notes=notes,
            )
            db.add(schedule)
            db.commit()
            db.refresh(schedule)
            return schedule
        except Exception:
            db.rollback()
            return None

    def create_schedule_from_request(
        self,
        db: Session,
        user_id: int,
        request: HarvestScheduleCreateRequest,
    ) -> dict | None:
        try:
            from app.models.harvest import HarvestSchedule

            crop = ensure_crop(db, request.crop_name)
            expected_date = request.expected_harvest_date
            if expected_date is None:
                expected_date = request.planting_date + timedelta(days=self._resolve_growth_days(db, request.crop_name))

            schedule = HarvestSchedule(
                UserID=user_id,
                CropID=crop.CropID,
                Region=request.region,
                PlantingDate=request.planting_date,
                ExpectedHarvestDate=expected_date,
                AreaSize=request.area_size,
                EstimatedYieldKg=request.estimated_yield_kg,
                FertilizerUsed=request.fertilizer_used,
                PesticideUsed=request.pesticide_used,
                Notes=request.notes,
            )
            db.add(schedule)
            db.commit()
            db.refresh(schedule)
            return self._schedule_to_dict(schedule, crop)
        except Exception:
            db.rollback()
            return None

    def get_history(self, db: Session, user_id: int, limit: int = 50) -> list[dict]:
        records = get_harvest_forecast_history(db, user_id, limit)
        return [
            {
                "forecast_id": forecast.id,
                "schedule_id": schedule.id,
                "user_id": schedule.user_id,
                "crop_id": crop.id,
                "crop_name": crop.name,
                "region": schedule.region,
                "planting_date": schedule.planting_date,
                "expected_harvest_date": forecast.expected_harvest_date,
                "confidence": forecast.confidence_score,
                "warning": forecast.weather_warning,
                "recommendation": forecast.labor_recommendation,
                "transport_recommendation": forecast.transport_recommendation,
                "model_version": forecast.model_version,
                "generated_at": forecast.generated_at,
            }
            for forecast, schedule, crop in records
        ]

    def get_schedules(self, db: Session, user_id: int, limit: int = 50) -> list[dict]:
        records = get_harvest_schedules_by_user(db, user_id, limit)
        return [
            self._schedule_to_dict(schedule, crop)
            for schedule, crop in records
        ]

    def optimize(self, db: Session, request: HarvestForecastRequest, user_id: int | None = None) -> dict:
        forecast = self.forecast_harvest(db, request, user_id=user_id)
        if forecast.get("_api_error"):
            return forecast
        try:
            from app.services.pricing_service import pricing_service
            pricing = pricing_service.build_pricing_engine(
                db,
                crop_name=request.crop_name,
                region=request.region,
                quantity=1,
                quality_grade="grade_1",
                days=7,
            )
        except Exception:
            pricing = {}
        recommendation = forecast["recommendation"]
        if pricing.get("trend") == "increasing" and forecast.get("weather_risk") != "high":
            recommendation = "Market trend is favorable; keep the optimal date and avoid rushing harvest."
        elif forecast.get("weather_risk") == "high":
            recommendation = "Weather risk is high; prepare labor and consider early harvest window."
        return {
            **forecast,
            "market_price": pricing.get("market_price"),
            "pricing_trend": pricing.get("trend"),
            "recommendation": recommendation,
            "source": "ai_generated" if not forecast.get("is_mock") else "mock",
            "source_name": "AI Harvest Optimizer",
            "confidence": min(float(forecast.get("confidence") or 0.7), float(pricing.get("confidence") or 0.7)),
        }

    def calendar(self, db: Session, user_id: int | None = None, limit: int = 50) -> dict:
        resolved_user = user_id or 1
        schedules = self.get_schedules(db, resolved_user, limit)
        items = [
            {
                "schedule_id": schedule.get("schedule_id"),
                "crop_name": schedule.get("crop_name"),
                "region": schedule.get("region"),
                "date": schedule.get("expected_harvest_date"),
                "type": "harvest",
                "status": schedule.get("status"),
                "source": "database",
                "source_name": "HarvestSchedule DB",
            }
            for schedule in schedules
        ]
        return {
            "user_id": resolved_user,
            "items": items,
            "total": len(items),
            "source": "database",
            "source_name": "HarvestSchedule DB",
            "confidence": 0.7,
            "cache_status": "from_db",
        }

    def risk_for_season(self, db: Session, season_id: int) -> dict:
        try:
            from app.models.harvest import HarvestSchedule
            schedule = db.query(HarvestSchedule).filter(HarvestSchedule.ScheduleID == season_id).first()
        except Exception:
            schedule = None
        if not schedule:
            if self._realtime_only():
                return {
                    "_api_error": True,
                    "error_code": "REALTIME_API_FAILED",
                    "error_message": "Không thể tải rủi ro mùa vụ realtime. Vui lòng thử lại sau.",
                    "source": "realtime_api",
                }
            return {
                "season_id": season_id,
                "risk_level": "medium",
                "weather_risk": "medium",
                "market_condition": "neutral",
                "recommended_action": ["Review season data; schedule not found so demo risk is returned."],
                "source": "mock",
                "source_name": "Harvest risk fallback",
                "is_mock": True,
                "confidence": 0.35,
            }
        crop_name = "crop"
        region = schedule.Region
        weather_risk = self._weather_risk_label(db, region)
        market_condition = self._market_condition(db, crop_name, region)
        risk_level = "high" if weather_risk == "high" else "medium" if market_condition == "unfavorable" else "low"
        return {
            "season_id": season_id,
            "risk_level": risk_level,
            "weather_risk": weather_risk,
            "market_condition": market_condition,
            "recommended_action": self._preparation_tasks(crop_name, schedule.ExpectedHarvestDate)[:3],
            "source": "ai_generated",
            "source_name": "Harvest risk rule engine",
            "confidence": 0.68,
            "cache_status": "computed",
        }

    @staticmethod
    def _schedule_to_dict(schedule, crop) -> dict:
        return {
            "schedule_id": schedule.id,
            "user_id": schedule.user_id,
            "crop_id": crop.id,
            "crop_name": crop.name,
            "crop_image": getattr(crop, "image_url", None),
            "planting_date": schedule.planting_date,
            "area_size": schedule.area_size,
            "unit": "hectare",
            "region": schedule.region,
            "expected_harvest_date": schedule.expected_harvest_date,
            "actual_harvest_date": schedule.actual_harvest_date,
            "estimated_yield_kg": schedule.estimated_yield_kg,
            "actual_yield_kg": schedule.actual_yield_kg,
            "fertilizer_used": getattr(schedule, "FertilizerUsed", None),
            "pesticide_used": getattr(schedule, "PesticideUsed", None),
            "status": schedule.status,
            "notes": schedule.notes,
            "created_at": schedule.created_at,
            "updated_at": schedule.updated_at,
        }

    def _growth_days_for(self, crop_name: str) -> int:
        key = self._normalize_key(crop_name)
        return self.default_growth_days.get(key, 120)  # default 120 ngày thay vì 70

    def _get_growth_stages(self, crop_name: str) -> list[str]:
        key = self._normalize_key(crop_name)
        return self._growth_stages.get(key, [])

    def _resolve_growth_days(self, db: Session, crop_name: str) -> int:
        key = self._normalize_key(crop_name)
        if key in self.default_growth_days:
            return self.default_growth_days[key]
        return self._get_crop_growth_days(db, crop_name) or self._growth_days_for(crop_name)

    def _get_crop_growth_days(self, db: Session, crop_name: str) -> Optional[int]:
        try:
            from app.models.crop import CropType

            crop = db.query(CropType).filter(CropType.CropName == crop_name).first()
            return crop.GrowthDurationDays if crop and crop.GrowthDurationDays else None
        except Exception:
            return None

    @staticmethod
    def _get_latest_weather(db: Session, region: str) -> Optional[Dict]:
        try:
            from app.services.weather_service import weather_service

            weather = weather_service.get_current_weather(db, region)
            return {
                "temperature": float(weather["temperature"]) if weather.get("temperature") is not None else None,
                "rainfall": float(weather["rainfall"]) if weather.get("rainfall") is not None else None,
                "humidity": float(weather["humidity"]) if weather.get("humidity") is not None else None,
                "source": weather.get("source"),
                "source_name": weather.get("source_name"),
                "fetched_at": weather.get("fetched_at") or weather.get("last_updated"),
                "updated_at": weather.get("updated_at") or weather.get("last_updated"),
                "is_mock": weather.get("is_mock", True),
            }
        except Exception:
            return None

    @staticmethod
    def _normalize_key(value: str) -> str:
        normalized = normalize("NFD", value.strip().lower())
        return "".join(char for char in normalized if category(char) != "Mn")

    @staticmethod
    def _warning_for(expected_date: date) -> str | None:
        if expected_date.month in {9, 10, 11}:
            return "Mùa mưa bão, cần theo dõi thời tiết và chuẩn bị thu hoạch sớm nếu cần."
        return None

    def _weather_risk_label(self, db: Session, region: str) -> str:
        try:
            from app.services.weather_service import weather_service
            risk = weather_service.analyze_agriculture_risk(db, region, "crop")
            return risk.get("risk_level", "medium")
        except Exception:
            return "medium"

    def _market_condition(self, db: Session, crop_name: str, region: str) -> str:
        try:
            from app.services.pricing_service import pricing_service
            trend = pricing_service.analyze_price_trend(db, crop_name, region)
            if trend == "increasing":
                return "favorable"
            if trend == "decreasing":
                return "unfavorable"
        except Exception:
            pass
        return "neutral"

    @staticmethod
    def _preparation_tasks(crop_name: str, expected_date: date) -> list[str]:
        return [
            f"Xác nhận nhân công thu hoạch trước ngày {expected_date.isoformat()} khoảng 7 ngày.",
            f"Chuẩn bị bao bì và vệ sinh khu vực bảo quản cho {crop_name}.",
            "Kiểm tra dự báo thời tiết 3 ngày trước khi cắt hoặc thu gom.",
            "Tạo cảnh báo giá theo mức giá bán mục tiêu.",
        ]


harvest_service = HarvestService()
