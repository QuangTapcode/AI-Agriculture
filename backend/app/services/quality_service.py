"""
Quality Service - merged Tien (repository + pricing) + Quang (AI detector + DB records)
- API endpoint dùng: check_quality(db, *, image_path, crop_name, region)
- Thử AI detector trước, fallback về mock_grade
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.common import normalize_text, to_api_grade
from app.repositories.quality_repository import (
    create_quality_check,
    get_quality_check_by_id,
    get_quality_checks_by_user,
)
from app.schemas.price_schema import PricingSuggestRequest
from app.services.pricing_service import pricing_service


class QualityService:
    """Service kiểm tra chất lượng nông sản qua ảnh."""

    # ------------------------------------------------------------------ #
    # API interface
    # ------------------------------------------------------------------ #

    def check_quality(
        self,
        db: Session,
        image_path: str,
        crop_name: str,
        region: str,
        user_id: Optional[int] = None,
    ) -> dict:
        """
        Kiểm tra chất lượng nông sản:
        1. Gemini Vision phân tích ảnh thực tế (màu sắc, khuyết tật, loại nông sản)
        2. Lấy pricing từ pricing_service
        3. Lưu kết quả qua repository
        4. Trả về kết quả đầy đủ
        """
        normalized_region = self._normalize_region(region)

        # 1. Phân tích ảnh — ưu tiên YOLO+EfficientNet (local), fallback Gemini Vision
        vision_result = self._run_yolo_pipeline(image_path, crop_name=crop_name)
        _used_source = "yolo_efficientnet"

        if vision_result is None and crop_name:
            # YOLO không detect bbox nhưng user cung cấp crop_name
            # → classify toàn ảnh bằng EfficientNet + HSV
            try:
                from ai_models.fruit_quality_pipeline import fruit_quality_pipeline
                det = fruit_quality_pipeline.classify_full_image(image_path, crop_name_hint=crop_name)
                if det and det.get("confidence", 0) > 0:
                    grade_map = {"grade_1": "grade_1", "grade_2": "grade_2",
                                 "grade_3": "grade_3", "damaged": "damaged"}
                    grade = grade_map.get(det["grade"], "grade_2")
                    vision_result = {
                        "detected_crop": det["fruit_type_vi"],
                        "is_produce": True,
                        "color_assessment": f"Màu {det.get('hsv_color', '?')}, độ tươi {det.get('hsv_freshness', 0):.0%}",
                        "ripeness": det["quality_level"],
                        "defects": [],
                        "quality_grade": grade,
                        "confidence": det["confidence"],
                        "reasoning": det.get("reasoning", ""),
                        "yolo_confidence": 0.0,
                        "efficientnet_confidence": det.get("efficientnet_confidence", 0),
                        "efficientnet_top3": str(det.get("efficientnet_top3", "")),
                        "hsv_freshness": det.get("hsv_freshness", 0),
                        "total_detections": 0,
                        "source": "efficientnet_fullimage",
                    }
                    _used_source = "efficientnet_fullimage"
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning("[QualityService] classify_full_image failed: %s", exc)

        if vision_result is None:
            # YOLO không detect quả → thử Gemini Vision
            _used_source = "gemini_vision"
            analyzer = self._get_detector()
            if analyzer is None:
                if self._realtime_only():
                    return {
                        "_api_error": True,
                        "error_code": "REALTIME_API_FAILED",
                        "error_message": "Không thể kết nối AI kiểm định chất lượng. Vui lòng thử lại sau.",
                        "source": "realtime_api",
                    }
                grade, confidence, defects = self._mock_grade(image_path)
                vision_result = {
                    "detected_crop": crop_name or "unknown",
                    "is_produce": True,
                    "color_assessment": "",
                    "ripeness": "unknown",
                    "defects": defects,
                    "quality_grade": grade,
                    "confidence": confidence,
                    "reasoning": "mock fallback",
                }
                _used_source = "mock"
            else:
                try:
                    with open(image_path, "rb") as f:
                        image_bytes = f.read()
                    if hasattr(analyzer, "analyze"):
                        vision_result = analyzer.analyze(image_bytes)
                    else:
                        detector_result = analyzer.analyze_image(image_path, crop_name)
                        vision_result = self._vision_from_detector_result(detector_result, crop_name)
                except Exception as e:
                    if self._realtime_only():
                        return {
                            "_api_error": True,
                            "error_code": "REALTIME_API_FAILED",
                            "error_message": "Không thể kết nối AI kiểm định chất lượng. Vui lòng thử lại sau.",
                            "source": "realtime_api",
                        }
                    vision_result = {
                        "detected_crop": "không xác định",
                        "is_produce": False,
                        "color_assessment": f"Lỗi đọc ảnh: {e}",
                        "ripeness": "unknown",
                        "defects": [],
                        "quality_grade": "grade_2",
                        "confidence": 0.0,
                        "reasoning": str(e),
                    }
                    _used_source = "fallback"

        detected_crop = vision_result.get("detected_crop", "không xác định")
        is_produce = vision_result.get("is_produce", False)
        grade = vision_result.get("quality_grade", "grade_2")
        confidence = vision_result.get("confidence", 0.0)
        defects = vision_result.get("defects", [])
        color_assessment = vision_result.get("color_assessment", "")
        reasoning = vision_result.get("reasoning", "")
        if self._realtime_only() and float(confidence or 0) <= 0:
            return {
                "_api_error": True,
                "error_code": "REALTIME_API_FAILED",
                "error_message": "Không thể kết nối AI kiểm định chất lượng. Vui lòng thử lại sau.",
                "source": "realtime_api",
            }
        disease_detected = bool(defects)
        damage_level = self._damage_level(grade)

        effective_crop = crop_name if crop_name and crop_name not in ("unknown", "") else detected_crop

        pricing = self._get_quality_pricing(
            db=db,
            crop_name=effective_crop,
            region=normalized_region,
            grade=grade,
        )
        price_unavailable = bool(pricing.get("_api_error"))

        final_min = pricing.get("weather_min_price")
        if final_min is None:
            final_min = pricing.get("min_price")

        final_max = pricing.get("weather_max_price")
        if final_max is None:
            final_max = pricing.get("max_price")

        final_suggested = pricing.get("weather_suggested_price")
        if final_suggested is None:
            final_suggested = pricing.get("suggested_price")

        if final_min is None or final_max is None:
            suggested_range = pricing.get("suggested_price_range") or {}
            final_min = final_min if final_min is not None else suggested_range.get("min")
            final_max = final_max if final_max is not None else suggested_range.get("max")

        stored_suggested_price = final_suggested if self._has_positive_price(final_suggested) else None
        stored_min_price = final_min if self._has_positive_price(final_min) else None
        stored_max_price = final_max if self._has_positive_price(final_max) else None

        record = create_quality_check(
            db,
            crop_name=effective_crop,
            region=normalized_region,
            image_path=image_path,
            quality_grade=grade,
            disease_detected=disease_detected,
            damage_level=damage_level,
            suggested_price=stored_suggested_price,
            suggested_price_min=stored_min_price,
            suggested_price_max=stored_max_price,
            confidence=confidence,
            user_id=user_id,
        )

        self._save_quality_record_direct(
            db=db,
            crop_name=effective_crop,
            user_id=user_id,
            image_path=image_path,
            grade=grade,
            confidence=confidence,
            defects=defects,
            min_price=stored_min_price,
            max_price=stored_max_price,
            recommendations=self._recommendations(grade),
        )

        source_is_mock = (_used_source == "mock") or (reasoning == "mock fallback")
        quality_multiplier = pricing.get("quality_coefficient")
        if quality_multiplier is None:
            quality_multiplier = pricing.get("quality_multiplier", 1.0)

        return {
            "crop_name": effective_crop,
            "detected_crop": detected_crop,
            "is_produce": is_produce,
            "color_assessment": color_assessment,
            "reasoning": reasoning,
            "region": normalized_region,
            "image_path": image_path,
            "quality_grade": grade,
            "quality_grade_letter": self._grade_letter(grade),
            "disease_detected": disease_detected,
            "disease_risk": damage_level,
            "damage_level": damage_level,
            "freshness_score": self._freshness_score(grade, defects),
            "suggested_price": final_suggested,
            "suggested_price_adjustment": f"{int(((quality_multiplier or 1.0) - 1) * 100)}%",
            "confidence": confidence,
            "defects": defects,
            "suggested_price_range": {
                "min": final_min,
                "max": final_max,
            },
            "price_source": pricing.get("source", "unavailable" if price_unavailable else ""),
            "price_unavailable": price_unavailable,
            "quality_multiplier": quality_multiplier or 1.0,
            "weather_factor": pricing.get("weather_factor", 1.0),
            "weather_summary": pricing.get("weather_summary", ""),
            "weather_explanation": pricing.get("weather_explanation", ""),
            "price_change_pct": pricing.get("price_change_pct", 0.0),
            "recommendation": self._recommendations(grade),
            "recommendations": self._recommendations(grade),
            "ai_source": _used_source,
            "yolo_confidence": vision_result.get("yolo_confidence", 0),
            "efficientnet_confidence": vision_result.get("efficientnet_confidence", 0),
            "efficientnet_top3": vision_result.get("efficientnet_top3", ""),
            "hsv_freshness": vision_result.get("hsv_freshness", 0),
            "total_detections": vision_result.get("total_detections", 0),
            "all_detections": vision_result.get("all_detections", []),
            "annotated_b64": vision_result.get("annotated_b64", ""),
            "source": "mock" if source_is_mock else "ai_generated",
            "source_name": (
                "YOLO11 + EfficientNet + HSV" if _used_source == "yolo_efficientnet"
                else "EfficientNet full image" if _used_source == "efficientnet_fullimage"
                else "Gemini Vision Quality" if _used_source == "gemini_vision"
                else "Rule-based fallback"
            ),
            "is_mock": source_is_mock,
            "cache_status": "computed",
            "checked_at": getattr(record, "checked_at", None) or datetime.now(),
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _realtime_only() -> bool:
        return bool(settings.USE_REALTIME_ONLY) and not bool(settings.ALLOW_MOCK_DATA or settings.ALLOW_SAMPLE_DATA)

    @staticmethod
    def _normalize_region(region: str | None) -> str:
        return pricing_service._clean_region(region)

    @staticmethod
    def _has_positive_price(value) -> bool:
        try:
            return value is not None and float(value) > 0
        except (TypeError, ValueError):
            return False

    def _get_quality_pricing(self, db: Session, crop_name: str, region: str, grade: str) -> dict:
        normalized_region = self._normalize_region(region)
        request = PricingSuggestRequest(
            crop_name=crop_name,
            region=normalized_region,
            quantity=1,
            quality_grade=grade,
        )
        try:
            pricing = pricing_service.suggest_price(db, request)
            if pricing and not pricing.get("_api_error"):
                return pricing
        except Exception:
            pass
        return {
            "_api_error": True,
            "source": "realtime_api",
            "weather_factor": 1.0,
            "weather_summary": "",
            "weather_explanation": "",
            "price_change_pct": 0.0,
        }

    @staticmethod
    def _run_yolo_pipeline(image_path: str, crop_name: str = "") -> dict | None:
        """Run YOLO11+EfficientNet+HSV pipeline.

        Returns a vision_result dict (same shape as Gemini result) when at least
        one fruit is detected, or None when the image has no detectable fruit.
        """
        try:
            from ai_models.fruit_quality_pipeline import fruit_quality_pipeline
            result = fruit_quality_pipeline.analyze(image_path, crop_name_hint=crop_name)
            detections = result.get("detections", [])
            if not detections:
                return None   # caller decides: try classify_full_image or Gemini

            best = max(detections, key=lambda d: d["confidence"])

            _GRADE_MAP = {
                "grade_1": "grade_1", "grade_2": "grade_2",
                "grade_3": "grade_3", "damaged": "damaged",
            }
            grade = _GRADE_MAP.get(best["grade"], "grade_2")

            defects: list[str] = []
            if best.get("hsv_defect_ratio", 0) > 0.10:
                defects.append("vùng tối / tổn thương màu sắc")
            if best.get("color_uniformity", 1.0) < 0.50:
                defects.append("màu sắc không đồng đều")
            if grade in ("grade_3", "damaged"):
                defects.append("chất lượng thấp")

            top3_text = ", ".join(
                f"{n} {p:.0%}" for n, p in best.get("efficientnet_top3", [])[:3]
            )

            return {
                "detected_crop": best["fruit_type_vi"],
                "is_produce": True,
                "color_assessment": f"Màu {best.get('hsv_color', '?')}, "
                                    f"độ tươi {best.get('hsv_freshness', 0):.0%}",
                "ripeness": best["quality_level"],
                "defects": defects,
                "quality_grade": grade,
                "confidence": best["confidence"],
                "reasoning": best.get("reasoning", ""),
                "yolo_confidence": best.get("yolo_confidence", 0),
                "efficientnet_confidence": best.get("efficientnet_confidence", 0),
                "efficientnet_top3": top3_text,
                "hsv_freshness": best.get("hsv_freshness", 0),
                "total_detections": len(detections),
                "all_detections": detections,
                "annotated_b64": result.get("annotated_b64", ""),
                "source": "yolo_efficientnet",
            }
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("[QualityService] YOLO pipeline failed: %s", exc)
            return None

    @staticmethod
    def _get_detector():
        from app.integrations.gemini_vision_quality import GeminiVisionAnalyzer
        return GeminiVisionAnalyzer()

    @staticmethod
    def _vision_from_detector_result(result: dict, crop_name: str) -> dict:
        grade = result.get("quality_grade", "grade_2")
        defects = result.get("defects", [])
        return {
            "detected_crop": crop_name or "unknown",
            "is_produce": True,
            "color_assessment": "",
            "ripeness": "unknown",
            "defects": defects,
            "quality_grade": grade,
            "confidence": result.get("confidence", 0.0),
            "reasoning": ", ".join(defects) if defects else "",
        }

    @staticmethod
    def _save_quality_record_direct(
        db: Session,
        crop_name: str,
        user_id: Optional[int],
        image_path: str,
        grade: str,
        confidence: float,
        defects: list,
        min_price: float | None,
        max_price: float | None,
        recommendations: list,
    ):
        """Lưu vào bảng QualityRecords trực tiếp (Quang) - best-effort."""
        if not user_id:
            return
        _GRADE_MAP = {"grade_1": "Loai 1", "grade_2": "Loai 2", "grade_3": "Loai 3"}
        db_grade = _GRADE_MAP.get(grade, "Loai 2")
        try:
            from app.models.quality import QualityRecord
            from app.models.crop import CropType
            crop = db.query(CropType).filter(CropType.CropName.ilike(f"%{crop_name}%")).first()
            if not crop:
                return
            record = QualityRecord(
                UserID=user_id,
                CropID=crop.CropID,
                ImagePath=image_path,
                AIGrade=db_grade,
                ConfidenceScore=confidence,
                DetectedIssues=json.dumps(defects, ensure_ascii=False),
                SuggestedPriceMin=min_price,
                SuggestedPriceMax=max_price,
                Recommendation="\n".join(recommendations),
            )
            db.add(record)
            db.commit()
        except Exception as exc:
            db.rollback()
            print(f"Warning: cannot save QualityRecord: {exc}")

    def get_history(self, db: Session, user_id: int, limit: int = 50) -> list[dict]:
        return [
            self._record_to_dict(record, crop)
            for record, crop in get_quality_checks_by_user(db, user_id, limit)
        ]

    def get_detail(self, db: Session, record_id: int) -> dict | None:
        result = get_quality_check_by_id(db, record_id)
        if result is None:
            return None
        record, crop = result
        return self._record_to_dict(record, crop)

    _GRADE_MULTIPLIER = {"grade_1": 1.0, "grade_2": 0.78, "grade_3": 0.45}

    def _fetch_real_price(self, db: Session, crop_name: str, region: str, grade: str) -> dict:
        """
        Lấy giá thực từ MarketPrices DB cho crop_name.
        Áp hệ số chất lượng: grade_1=100%, grade_2=78%, grade_3=45%.
        Không bịa dữ liệu khi không lấy được giá thật.
        """
        from app.models.crop import Crop
        from app.models.price import MarketPrice

        multiplier = self._GRADE_MULTIPLIER.get(grade, 0.78)
        normalized_region = self._normalize_region(region)
        target_region = normalize_text(normalized_region)

        crop = (
            db.query(Crop)
            .filter(Crop.CropName.ilike(f"%{crop_name}%"))
            .first()
        )

        base_price: float | None = None
        source = "market_db"

        if crop:
            rows = (
                db.query(MarketPrice)
                .filter(MarketPrice.CropID == crop.CropID)
                .order_by(MarketPrice.PriceDate.desc(), MarketPrice.UpdatedAt.desc())
                .all()
            )
            mp = next((row for row in rows if normalize_text(row.Region) == target_region), None)
            if not mp and rows:
                mp = rows[0]
            if mp:
                base_price = float(mp.PricePerKg)
                source = "market_db"

        if base_price is None:
            try:
                import asyncio
                import re
                from app.integrations.tavily_client import ask_price_qa
                result = asyncio.run(asyncio.wait_for(asyncio.to_thread(
                    ask_price_qa,
                    f"giá {crop_name} hiện nay tại {normalized_region} VNĐ/kg"
                ), timeout=settings.AI_TIMEOUT_SECONDS))
                nums = re.findall(r'\d[\d\.]{2,8}', result.get("tavily_answer", ""))
                if nums:
                    base_price = float(nums[0].replace(".", ""))
                    source = "tavily"
            except Exception:
                pass

        if base_price is None:
            return {
                "_api_error": True,
                "error_code": "REALTIME_API_FAILED",
                "error_message": "Không thể tải giá realtime cho kiểm định chất lượng.",
                "source": "realtime_api",
            }

        suggested = round(base_price * multiplier)
        spread = 0.08
        return {
            "suggested": suggested,
            "min": round(suggested * (1 - spread)),
            "max": round(suggested * (1 + spread)),
            "base_price": base_price,
            "multiplier": multiplier,
            "source": source,
        }

    @staticmethod
    def _mock_grade(image_path: str) -> tuple[str, float, list[str]]:
        """Phân loại dựa trên tên file (fallback khi không có AI)."""
        lowered = image_path.lower()
        if "bad" in lowered or "grade3" in lowered or "grade_3" in lowered:
            return "grade_3", 0.68, ["surface_damage"]
        if "medium" in lowered or "grade2" in lowered or "grade_2" in lowered:
            return "grade_2", 0.76, ["minor_spot"]
        return "grade_1", 0.86, []

    @staticmethod
    def _damage_level(grade: str) -> str:
        return {"grade_1": "low", "Loại 1": "low",
                "grade_2": "medium", "Loại 2": "medium",
                "grade_3": "high", "Loại 3": "high"}.get(grade, "low")

    @staticmethod
    def _grade_letter(grade: str) -> str:
        return {
            "grade_1": "A",
            "Loai 1": "A",
            "Loại 1": "A",
            "grade_2": "B",
            "Loai 2": "B",
            "Loại 2": "B",
            "grade_3": "C",
            "Loai 3": "C",
            "Loại 3": "C",
        }.get(grade, "B")

    @staticmethod
    def _freshness_score(grade: str, defects: list) -> int:
        base = {"grade_1": 92, "grade_2": 72, "grade_3": 48}.get(grade, 70)
        return max(20, min(100, base - len(defects or []) * 6))

    @staticmethod
    def _recommendations(grade: str) -> list[str]:
        if grade in ("grade_1", "Loai 1", "Loại 1"):
            return [
                "Ưu tiên bán kênh siêu thị, cửa hàng sạch hoặc xuất khẩu.",
                "Đóng gói đẹp để tăng giá trị thương phẩm.",
            ]
        if grade in ("grade_2", "Loai 2", "Loại 2"):
            return [
                "Phù hợp cho chợ đầu mối hoặc thương lái địa phương.",
                "Giá bán thấp hơn ~22% so với loại 1.",
            ]
        return [
            "Nên bán nhanh hoặc chuyển sang kênh chế biến để giảm hao hụt.",
            "Giá bán chỉ đạt ~45% giá thị trường — cân nhắc làm nước ép, sấy khô.",
        ]

    @staticmethod
    def _record_to_dict(record, crop) -> dict:
        issues = QualityService._parse_issues(record.detected_issues)
        suggested_min = float(record.suggested_price_min or 0)
        suggested_max = float(record.suggested_price_max or 0)
        suggested_price = round((suggested_min + suggested_max) / 2, 2) if suggested_min or suggested_max else 0
        grade = to_api_grade(record.quality_grade)
        return {
            "record_id": record.RecordID,
            "schedule_id": record.ScheduleID,
            "user_id": record.UserID,
            "crop_id": crop.CropID,
            "crop_name": crop.CropName,
            "image_path": record.image_path,
            "quality_grade": grade,
            "disease_detected": bool(issues.get("disease_detected", False)),
            "damage_level": issues.get("damage_level") or QualityService._damage_level(grade),
            "suggested_price": suggested_price,
            "confidence": float(record.ConfidenceScore or 0),
            "defects": issues.get("defects", []),
            "suggested_price_range": {
                "min": suggested_min,
                "max": suggested_max,
            },
            "recommendation": record.Recommendation,
            "recommendations": QualityService._recommendations(grade),
            "checked_at": record.CheckDate,
        }

    @staticmethod
    def _parse_issues(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            issues = json.loads(raw)
        except (TypeError, ValueError):
            return {"defects": [raw]}
        if not isinstance(issues, dict):
            return {"defects": issues if isinstance(issues, list) else [str(issues)]}
        defects = issues.get("defects")
        if defects is None and issues.get("disease_detected"):
            defects = ["detected_issue"]
        return {**issues, "defects": defects or []}


quality_service = QualityService()
