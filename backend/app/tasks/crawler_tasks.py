"""
Auto-crawler chạy trong FastAPI background (asyncio task, không cần Celery).

Pipeline:
  [Cào web] → [Pre-filter & chuẩn hóa] → [Loại bỏ nhiễu] → [Ưu tiên nguồn] → [Upsert DB]
            ↗ [BachHoaXanh / WinMart — ưu tiên cao nhất]
            ↗ [giacaphe.com / giatieu.com — chuyên ngành]
            ↗ [nongnghiep.vn / gia.vn — tin tức]
            → [Simulation (fallback cuối cùng)]
"""
import asyncio
import logging
import os
import random
import re
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import httpx

from app.services.notification_service import notification_service

logger = logging.getLogger(__name__)

CRAWL_INTERVAL = int(os.getenv("CRAWL_INTERVAL_SECONDS", "3600"))  # mặc định 1 giờ
ADMIN_NOTIFICATION_EMAIL = os.getenv("ADMIN_NOTIFICATION_EMAIL", "admin@example.com")

# ─── Độ uy tín nguồn (thấp hơn = uy tín cao hơn) ──────────────────────────────
SOURCE_PRIORITY: Dict[str, int] = {
    "bachhoaxanh.com": 1,   # Siêu thị bán lẻ — giá chính xác, cập nhật hàng ngày
    "winmart.vn":      1,   # Siêu thị bán lẻ — giá chính xác, cập nhật hàng ngày
    "giacaphe.com":    2,   # Chuyên cà phê — uy tín cao
    "giatieu.com":     2,   # Chuyên hồ tiêu — uy tín cao
    "nongnghiep.vn":   3,   # Báo nông nghiệp — tin cậy
    "gia.vn":          3,   # Cổng giá tổng hợp
    "vigen.net.vn":    4,
    "cadulo.com":      4,
    "simulation":      99,  # Giả lập — chỉ dùng khi không có dữ liệu thật
}

# ─── Giá nền (VND/kg) — dùng khi web không phản hồi ──────────────────────────
_BASE_PRICES: Dict[str, Dict[str, float]] = {
    # ── Cây ăn quả / Cây lâu năm ──────────────────────────────────────────────
    "Sầu riêng":   {"Tiền Giang": 65000, "Đắk Lắk": 60000, "Bình Phước": 55000,
                    "Đà Nẵng": 68000, "TP.HCM": 75000, "Cần Thơ": 62000,
                    "Đồng Nai": 58000, "Lâm Đồng": 57000},
    "Xoài":        {"Đồng Tháp": 28000, "Tiền Giang": 25000, "TP.HCM": 32000,
                    "An Giang": 26000, "Đồng Nai": 30000, "Khánh Hòa": 27000},
    "Thanh long":  {"Bình Thuận": 20000, "Long An": 18000, "TP.HCM": 25000,
                    "Tiền Giang": 19000},
    "Chuối":       {"Đồng Nai": 12000, "Tiền Giang": 10000, "TP.HCM": 18000,
                    "Hà Nội": 20000, "Lâm Đồng": 11000},
    "Dứa":         {"Tiền Giang": 8000, "Long An": 7500, "TP.HCM": 12000,
                    "Kiên Giang": 7000},
    "Dưa hấu":     {"Long An": 12000, "Tây Ninh": 11000, "Bình Định": 10000,
                    "TP.HCM": 15000, "Quảng Ngãi": 10500},
    "Bơ":          {"Đắk Lắk": 35000, "Lâm Đồng": 38000, "Đắk Nông": 33000,
                    "Gia Lai": 34000},
    "Mít":         {"Tiền Giang": 22000, "Đồng Nai": 20000, "TP.HCM": 28000,
                    "Long An": 21000},
    "Ổi":          {"Bình Dương": 15000, "TP.HCM": 20000, "Hà Nội": 22000},
    "Nhãn":        {"Hưng Yên": 30000, "Tiền Giang": 25000, "TP.HCM": 35000},
    "Vải":         {"Bắc Giang": 25000, "Hải Dương": 22000, "Hà Nội": 30000},
    "Cam":         {"Hà Giang": 28000, "Nghệ An": 25000, "TP.HCM": 35000,
                    "Hà Nội": 32000},
    "Bưởi":        {"Bến Tre": 20000, "Vĩnh Long": 18000, "TP.HCM": 28000,
                    "Hà Nội": 30000},
    # ── Rau củ ngắn ngày ───────────────────────────────────────────────────────
    "Cà chua":     {"Lâm Đồng": 18000, "Hà Nội": 22000, "TP.HCM": 25000,
                    "Đà Lạt": 16000, "Hải Dương": 20000},
    "Rau muống":   {"TP.HCM": 9000, "Hà Nội": 10000, "Cần Thơ": 8000,
                    "Đà Nẵng": 9500},
    "Rau cải":     {"TP.HCM": 12000, "Hà Nội": 14000, "Đà Lạt": 10000,
                    "Cần Thơ": 11000, "Đà Nẵng": 13000},
    "Cải bắp":     {"Lâm Đồng": 8000, "Hà Nội": 12000, "TP.HCM": 14000,
                    "Đà Nẵng": 10000},
    "Cải thảo":    {"Lâm Đồng": 10000, "Hà Nội": 13000, "TP.HCM": 15000},
    "Xà lách":     {"Đà Lạt": 15000, "TP.HCM": 20000, "Hà Nội": 22000},
    "Rau cần":     {"Hà Nội": 20000, "TP.HCM": 22000, "Hải Dương": 18000},
    "Hành lá":     {"TP.HCM": 25000, "Hà Nội": 28000, "Đà Nẵng": 23000},
    "Hành tây":    {"TP.HCM": 18000, "Hà Nội": 20000, "Đà Nẵng": 17000},
    "Tỏi":         {"Lý Sơn": 65000, "TP.HCM": 45000, "Hà Nội": 50000},
    "Gừng":        {"TP.HCM": 30000, "Hà Nội": 35000, "Nghệ An": 28000},
    "Nghệ":        {"TP.HCM": 25000, "Hà Nội": 30000, "Bình Định": 22000},
    "Cà rốt":      {"Lâm Đồng": 12000, "Hà Nội": 15000, "TP.HCM": 18000,
                    "Hải Dương": 11000},
    "Khoai tây":   {"Lâm Đồng": 15000, "Hà Nội": 18000, "TP.HCM": 22000},
    "Khoai lang":  {"Vĩnh Long": 15000, "Đồng Tháp": 14000, "TP.HCM": 18000,
                    "Bình Dương": 16000},
    "Su hào":      {"Hà Nội": 8000, "Lâm Đồng": 6000, "TP.HCM": 10000},
    "Củ cải":      {"Hà Nội": 10000, "Lâm Đồng": 8000, "TP.HCM": 12000},
    "Bí đỏ":       {"Lâm Đồng": 8000, "TP.HCM": 12000, "Hà Nội": 10000},
    "Bí xanh":     {"TP.HCM": 8000, "Hà Nội": 9000, "Đà Nẵng": 8500},
    "Bầu":         {"TP.HCM": 8000, "Hà Nội": 9000, "Cần Thơ": 7500},
    "Mướp":        {"TP.HCM": 10000, "Hà Nội": 12000, "Cần Thơ": 9000},
    "Khổ qua":     {"TP.HCM": 15000, "Hà Nội": 18000, "Đà Nẵng": 14000},
    "Đậu cove":    {"Lâm Đồng": 18000, "TP.HCM": 22000, "Hà Nội": 25000},
    "Đậu đũa":     {"TP.HCM": 18000, "Hà Nội": 20000, "Cần Thơ": 16000},
    "Ớt":          {"Gia Lai": 30000, "Bình Định": 28000, "Đồng Nai": 32000,
                    "TP.HCM": 35000, "Đà Nẵng": 30000},
    "Cải xoong":   {"Hà Nội": 25000, "TP.HCM": 28000, "Lâm Đồng": 22000},
    "Mồng tơi":    {"TP.HCM": 10000, "Hà Nội": 12000, "Cần Thơ": 9000},
    "Rau ngót":    {"TP.HCM": 15000, "Hà Nội": 18000},
    "Ngó sen":     {"TP.HCM": 35000, "Cần Thơ": 30000, "Đồng Tháp": 28000},
    # ── Ngũ cốc ────────────────────────────────────────────────────────────────
    "Lúa":         {"Cần Thơ": 8500, "Đồng Tháp": 8200, "Hà Nội": 7800,
                    "TP.HCM": 7500, "An Giang": 8300, "Kiên Giang": 8400,
                    "Long An": 8100, "Tiền Giang": 8000, "Vĩnh Long": 8200},
    "Ngô":         {"Đắk Lắk": 6500, "Gia Lai": 6200, "Sơn La": 6800,
                    "Hà Nội": 7000, "Nghệ An": 6300},
    # ── Cây công nghiệp ────────────────────────────────────────────────────────
    "Cà phê":      {"Đắk Lắk": 110000, "Gia Lai": 108000, "Đắk Nông": 107000,
                    "Lâm Đồng": 105000, "Kon Tum": 106000},
    "Hồ tiêu":     {"Gia Lai": 75000, "Bình Phước": 73000, "Đắk Lắk": 72000,
                    "Đắk Nông": 71000, "Đồng Nai": 74000},
    "Điều":        {"Bình Phước": 42000, "Đồng Nai": 41000, "Đắk Lắk": 40000,
                    "Gia Lai": 39000},
    "Mía":         {"Long An": 1100, "Tây Ninh": 1050, "Sóc Trăng": 1150,
                    "Hậu Giang": 1100},
}

# ─── Bảng alias → tên chuẩn trong DB ─────────────────────────────────────────
_CROP_ALIAS: Dict[str, str] = {
    # Sầu riêng
    "sầu riêng": "Sầu riêng", "sau rieng": "Sầu riêng", "sầu-riêng": "Sầu riêng",
    "musang king": "Sầu riêng", "ri6": "Sầu riêng", "monthong": "Sầu riêng",
    "durian": "Sầu riêng",
    # Xoài
    "xoài": "Xoài", "xoai": "Xoài", "mango": "Xoài",
    "xoài cát": "Xoài", "xoài tượng": "Xoài", "xoài gl6": "Xoài",
    # Thanh long
    "thanh long": "Thanh long", "dragon fruit": "Thanh long",
    "thanh long ruột đỏ": "Thanh long", "thanh long ruột trắng": "Thanh long",
    # Chuối
    "chuối": "Chuối", "chuoi": "Chuối", "banana": "Chuối",
    "chuối già": "Chuối", "chuối tiêu": "Chuối",
    # Dứa
    "dứa": "Dứa", "dua": "Dứa", "khóm": "Dứa", "kom": "Dứa", "pineapple": "Dứa",
    # Dưa hấu
    "dưa hấu": "Dưa hấu", "dua hau": "Dưa hấu", "watermelon": "Dưa hấu",
    # Bơ
    "bơ": "Bơ", "avocado": "Bơ", "bơ booth": "Bơ", "bơ 034": "Bơ",
    # Mít
    "mít": "Mít", "mit": "Mít", "jackfruit": "Mít", "mít thái": "Mít",
    # Ổi
    "ổi": "Ổi", "oi": "Ổi", "guava": "Ổi",
    # Nhãn
    "nhãn": "Nhãn", "nhan": "Nhãn", "longan": "Nhãn",
    # Vải
    "vải": "Vải", "vai": "Vải", "lychee": "Vải", "litchi": "Vải",
    # Cam
    "cam": "Cam", "orange": "Cam", "cam sành": "Cam", "cam vinh": "Cam",
    # Bưởi
    "bưởi": "Bưởi", "buoi": "Bưởi", "pomelo": "Bưởi",
    "bưởi da xanh": "Bưởi", "bưởi năm roi": "Bưởi",
    # Cà chua
    "cà chua": "Cà chua", "ca chua": "Cà chua", "tomato": "Cà chua",
    "cà chua bi": "Cà chua", "cà chua cherry": "Cà chua",
    # Rau muống
    "rau muống": "Rau muống", "rau muong": "Rau muống",
    # Rau cải (nhóm cải chung)
    "rau cải": "Rau cải", "cải xanh": "Rau cải", "cải ngọt": "Rau cải",
    "cải thìa": "Rau cải", "pak choi": "Rau cải",
    # Cải bắp
    "cải bắp": "Cải bắp", "bắp cải": "Cải bắp", "cabbage": "Cải bắp",
    # Cải thảo
    "cải thảo": "Cải thảo", "chinese cabbage": "Cải thảo",
    # Xà lách
    "xà lách": "Xà lách", "xa lach": "Xà lách", "lettuce": "Xà lách",
    "salad": "Xà lách",
    # Hành lá
    "hành lá": "Hành lá", "hanh la": "Hành lá", "spring onion": "Hành lá",
    "hành xanh": "Hành lá",
    # Hành tây
    "hành tây": "Hành tây", "hanh tay": "Hành tây", "onion": "Hành tây",
    # Tỏi
    "tỏi": "Tỏi", "toi": "Tỏi", "garlic": "Tỏi", "tỏi tươi": "Tỏi",
    # Gừng
    "gừng": "Gừng", "gung": "Gừng", "ginger": "Gừng",
    # Nghệ
    "nghệ": "Nghệ", "nghe": "Nghệ", "turmeric": "Nghệ",
    # Cà rốt
    "cà rốt": "Cà rốt", "ca rot": "Cà rốt", "carrot": "Cà rốt",
    # Khoai tây
    "khoai tây": "Khoai tây", "khoai tay": "Khoai tây", "potato": "Khoai tây",
    # Khoai lang
    "khoai lang": "Khoai lang", "sweet potato": "Khoai lang",
    # Su hào
    "su hào": "Su hào", "su hao": "Su hào", "kohlrabi": "Su hào",
    # Củ cải
    "củ cải": "Củ cải", "cu cai": "Củ cải", "daikon": "Củ cải",
    "củ cải trắng": "Củ cải",
    # Bí đỏ
    "bí đỏ": "Bí đỏ", "bi do": "Bí đỏ", "pumpkin": "Bí đỏ",
    "bí ngô": "Bí đỏ",
    # Bí xanh
    "bí xanh": "Bí xanh", "bi xanh": "Bí xanh",
    # Bầu
    "bầu": "Bầu", "bau": "Bầu", "bottle gourd": "Bầu",
    # Mướp
    "mướp": "Mướp", "muop": "Mướp", "luffa": "Mướp",
    "mướp hương": "Mướp", "mướp đắng": "Khổ qua",
    # Khổ qua
    "khổ qua": "Khổ qua", "kho qua": "Khổ qua", "bitter melon": "Khổ qua",
    "mướp đắng": "Khổ qua",
    # Đậu cove
    "đậu cove": "Đậu cove", "dau cove": "Đậu cove", "french bean": "Đậu cove",
    "đậu que": "Đậu cove",
    # Đậu đũa
    "đậu đũa": "Đậu đũa", "dau dua": "Đậu đũa", "yard-long bean": "Đậu đũa",
    # Ớt
    "ớt": "Ớt", "ot": "Ớt", "chili": "Ớt", "ớt chỉ thiên": "Ớt",
    "ớt đỏ": "Ớt", "ớt chuông": "Ớt",
    # Cải xoong
    "cải xoong": "Cải xoong", "watercress": "Cải xoong",
    # Mồng tơi
    "mồng tơi": "Mồng tơi", "mong toi": "Mồng tơi",
    # Rau ngót
    "rau ngót": "Rau ngót", "rau ngot": "Rau ngót",
    # Ngó sen
    "ngó sen": "Ngó sen", "ngo sen": "Ngó sen", "lotus root": "Ngó sen",
    # Lúa
    "lúa": "Lúa", "lua": "Lúa", "thóc": "Lúa",
    "lúa jasmine": "Lúa", "lúa ir50404": "Lúa", "gạo": "Lúa",
    # Ngô
    "ngô": "Ngô", "ngo": "Ngô", "bắp": "Ngô", "bap": "Ngô", "corn": "Ngô",
    # Cà phê
    "cà phê": "Cà phê", "ca phe": "Cà phê", "coffee": "Cà phê",
    "cà phê robusta": "Cà phê", "cà phê arabica": "Cà phê", "cafe": "Cà phê",
    # Hồ tiêu
    "hồ tiêu": "Hồ tiêu", "ho tieu": "Hồ tiêu", "tiêu": "Hồ tiêu",
    "pepper": "Hồ tiêu", "tiêu đen": "Hồ tiêu", "tiêu sọ": "Hồ tiêu",
    # Điều
    "điều": "Điều", "dieu": "Điều", "cashew": "Điều", "hạt điều": "Điều",
    # Mía
    "mía": "Mía", "mia": "Mía", "sugarcane": "Mía",
}

# ─── Bảng chuẩn hóa tỉnh/thành ────────────────────────────────────────────────
_REGION_ALIAS: Dict[str, str] = {
    "hồ chí minh": "TP.HCM", "tp hcm": "TP.HCM", "tp.hcm": "TP.HCM",
    "thành phố hồ chí minh": "TP.HCM", "ho chi minh": "TP.HCM", "hcm": "TP.HCM",
    "sài gòn": "TP.HCM",
    "hà nội": "Hà Nội", "hanoi": "Hà Nội", "ha noi": "Hà Nội",
    "đà nẵng": "Đà Nẵng", "da nang": "Đà Nẵng",
    "đắk lắk": "Đắk Lắk", "dak lak": "Đắk Lắk", "đắc lắc": "Đắk Lắk",
    "đắk nông": "Đắk Nông", "dak nong": "Đắk Nông",
    "gia lai": "Gia Lai",
    "kon tum": "Kon Tum",
    "lâm đồng": "Lâm Đồng", "lam dong": "Lâm Đồng",
    "đà lạt": "Lâm Đồng",
    "bình phước": "Bình Phước", "binh phuoc": "Bình Phước",
    "đồng nai": "Đồng Nai", "dong nai": "Đồng Nai",
    "bình dương": "Bình Dương", "binh duong": "Bình Dương",
    "tây ninh": "Tây Ninh", "tay ninh": "Tây Ninh",
    "tiền giang": "Tiền Giang", "tien giang": "Tiền Giang",
    "đồng tháp": "Đồng Tháp", "dong thap": "Đồng Tháp",
    "cần thơ": "Cần Thơ", "can tho": "Cần Thơ",
    "an giang": "An Giang",
    "kiên giang": "Kiên Giang", "kien giang": "Kiên Giang",
    "long an": "Long An",
    "bình thuận": "Bình Thuận", "binh thuan": "Bình Thuận",
    "vĩnh long": "Vĩnh Long", "vinh long": "Vĩnh Long",
    "sóc trăng": "Sóc Trăng", "soc trang": "Sóc Trăng",
    "hậu giang": "Hậu Giang", "hau giang": "Hậu Giang",
    "bến tre": "Bến Tre", "ben tre": "Bến Tre",
    "trà vinh": "Trà Vinh", "tra vinh": "Trà Vinh",
    "hải dương": "Hải Dương", "hai duong": "Hải Dương",
    "hưng yên": "Hưng Yên", "hung yen": "Hưng Yên",
    "bắc giang": "Bắc Giang", "bac giang": "Bắc Giang",
    "nghệ an": "Nghệ An", "nghe an": "Nghệ An",
    "bình định": "Bình Định", "binh dinh": "Bình Định",
    "khánh hòa": "Khánh Hòa", "khanh hoa": "Khánh Hòa",
    "quảng ngãi": "Quảng Ngãi", "quang ngai": "Quảng Ngãi",
    "lý sơn": "Lý Sơn",
    "sơn la": "Sơn La", "son la": "Sơn La",
    "hà giang": "Hà Giang", "ha giang": "Hà Giang",
}

# ─── Khoảng giá hợp lệ VND/kg (lọc nhiễu và lỗi parse) ──────────────────────
_PRICE_RANGE: Dict[str, Tuple[float, float]] = {
    # Cây ăn quả
    "Sầu riêng":  (20_000, 300_000),
    "Xoài":       (5_000,  120_000),
    "Thanh long": (3_000,  80_000),
    "Chuối":      (3_000,  50_000),
    "Dứa":        (3_000,  40_000),
    "Dưa hấu":    (2_000,  40_000),
    "Bơ":         (10_000, 150_000),
    "Mít":        (5_000,  80_000),
    "Ổi":         (5_000,  60_000),
    "Nhãn":       (15_000, 120_000),
    "Vải":        (15_000, 120_000),
    "Cam":        (10_000, 80_000),
    "Bưởi":       (8_000,  80_000),
    # Rau củ ngắn ngày
    "Cà chua":    (3_000,  80_000),
    "Rau muống":  (3_000,  30_000),
    "Rau cải":    (3_000,  50_000),
    "Cải bắp":    (2_000,  40_000),
    "Cải thảo":   (3_000,  50_000),
    "Xà lách":    (5_000,  80_000),
    "Rau cần":    (5_000,  60_000),
    "Hành lá":    (8_000,  100_000),
    "Hành tây":   (5_000,  80_000),
    "Tỏi":        (20_000, 200_000),
    "Gừng":       (10_000, 100_000),
    "Nghệ":       (10_000, 80_000),
    "Cà rốt":     (5_000,  60_000),
    "Khoai tây":  (8_000,  60_000),
    "Khoai lang": (3_000,  50_000),
    "Su hào":     (2_000,  30_000),
    "Củ cải":     (3_000,  40_000),
    "Bí đỏ":      (3_000,  50_000),
    "Bí xanh":    (3_000,  40_000),
    "Bầu":        (3_000,  35_000),
    "Mướp":       (4_000,  50_000),
    "Khổ qua":    (8_000,  80_000),
    "Đậu cove":   (8_000,  80_000),
    "Đậu đũa":    (8_000,  70_000),
    "Ớt":         (10_000, 200_000),
    "Cải xoong":  (10_000, 80_000),
    "Mồng tơi":   (5_000,  40_000),
    "Rau ngót":   (8_000,  60_000),
    "Ngó sen":    (20_000, 120_000),
    # Ngũ cốc
    "Lúa":        (4_000,  20_000),
    "Ngô":        (3_000,  20_000),
    # Cây công nghiệp
    "Cà phê":     (30_000, 250_000),
    "Hồ tiêu":    (30_000, 250_000),
    "Điều":       (20_000, 150_000),
    "Mía":        (500,    5_000),
}
_DEFAULT_PRICE_RANGE: Tuple[float, float] = (500, 2_000_000)


# ─── Tiện ích ─────────────────────────────────────────────────────────────────

def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


def _normalize_crop(raw: str) -> Optional[str]:
    """Trả về tên chuẩn hoặc None nếu không nhận dạng được."""
    from app.services.data_quality_service import normalize_crop_strict
    cleaned = re.sub(r"\s+", " ", _strip_tags(raw).strip())
    return normalize_crop_strict(cleaned)


def _normalize_region(raw: str) -> Optional[str]:
    """Trả về tên tỉnh chuẩn hoặc None."""
    cleaned = _strip_tags(raw).strip().lower()
    if cleaned in _REGION_ALIAS:
        return _REGION_ALIAS[cleaned]
    for alias, canonical in _REGION_ALIAS.items():
        if alias in cleaned:
            return canonical
    return None


def _parse_price_str(raw: str, unit_hint: str = "") -> Optional[float]:
    """
    Chuyển chuỗi giá → float (VND/kg).
    Xử lý: 65.000đ/kg, 65,000, 12.900đ/100g, 65k, 1kg=65000, v.v.
    """
    s = (raw + " " + unit_hint).strip().lower()

    multiplier = 1.0
    # Đơn vị nhỏ hơn kg → nhân lên
    if re.search(r"/\s*100\s*g", s):
        multiplier = 10.0
    elif re.search(r"/\s*200\s*g", s):
        multiplier = 5.0
    elif re.search(r"/\s*300\s*g", s):
        multiplier = 1000 / 300
    elif re.search(r"/\s*500\s*g", s):
        multiplier = 2.0
    # Đơn vị lớn hơn kg → chia xuống
    elif re.search(r"/\s*tấn|/\s*t\b", s):
        multiplier = 0.001
    elif re.search(r"/\s*tạ\b", s):
        multiplier = 0.01
    # Nghìn → nhân 1000
    elif re.search(r"nghìn|ngàn|k\b", s):
        multiplier = 1_000.0

    # Lấy phần số (xử lý dấu phẩy và chấm ngăn cách hàng nghìn)
    # VD: "65.000" → "65000"; "65,000" → "65000"; "65.5" → "65.5"
    num_str = re.sub(r"[^\d]", "", re.sub(r"(?<=\d)[.,](?=\d{3}(?:[^\d]|$))", "", raw.strip()))
    if not num_str:
        return None
    val = float(num_str) * multiplier
    return val if val > 0 else None


def _validate_price(price: float, crop_name: str) -> bool:
    lo, hi = _PRICE_RANGE.get(crop_name, _DEFAULT_PRICE_RANGE)
    return lo <= price <= hi


# ─── Pre-filter pipeline (chạy TRƯỚC khi lưu DB) ──────────────────────────────

def prefilter_items(raw_items: List[Dict]) -> List[Dict]:
    """
    Làm sạch và lọc danh sách giá thô trước khi lưu DB.

    Các bước:
    1. Bỏ bản ghi thiếu trường bắt buộc
    2. Validate khoảng giá hợp lệ cho từng loại cây
    3. Bỏ bản ghi trùng (crop+region) — giữ lại nguồn uy tín cao hơn
    4. Log thống kê sau khi lọc
    """
    if not raw_items:
        return []

    step1: List[Dict] = []
    for item in raw_items:
        crop = str(item.get("crop_name", "")).strip()
        region = str(item.get("region", "")).strip()
        price = item.get("price_per_kg", 0)
        source = str(item.get("source", "")).strip()
        price_date = item.get("date", date.today().isoformat())

        # Bước 1: kiểm tra trường bắt buộc
        if not crop or not region or not source:
            continue
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue

        # Bước 2: validate khoảng giá
        if not _validate_price(price, crop):
            logger.debug(
                f"[Filter] Loại bỏ giá bất thường: {crop} @ {region} = {price:,.0f}đ/kg "
                f"(nguồn: {source}) — ngoài khoảng hợp lệ"
            )
            continue

        step1.append({
            "crop_name": crop,
            "region": region,
            "price_per_kg": round(price, -2),
            "source": source,
            "date": price_date,
            "url": item.get("url", ""),
            "_priority": SOURCE_PRIORITY.get(source, 50),
        })

    # Bước 3: loại bỏ trùng — giữ nguồn có priority thấp nhất (= uy tín cao nhất)
    best: Dict[Tuple, Dict] = {}
    for item in step1:
        key = (item["crop_name"], item["region"])
        if key not in best or item["_priority"] < best[key]["_priority"]:
            best[key] = item

    result = list(best.values())
    for r in result:
        r.pop("_priority", None)

    discarded = len(raw_items) - len(result)
    logger.info(
        f"[Filter] Đầu vào: {len(raw_items)} | Hợp lệ: {len(result)} | Bị loại: {discarded}"
    )
    return result


# ─── Parsers từng nguồn ────────────────────────────────────────────────────────

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
}


def _make_item(crop: str, price: float, region: str, source: str, url: str = "") -> Dict:
    return {
        "crop_name": crop,
        "region": region,
        "price_per_kg": round(price, -2),
        "source": source,
        "date": date.today().isoformat(),
        "url": url,
    }


def _extract_and_add(
    name_raw: str, price_raw: str, region: str,
    source: str, results: List, seen: set,
    unit_hint: str = "", url: str = "",
) -> None:
    crop = _normalize_crop(name_raw)
    if not crop:
        return
    price = _parse_price_str(price_raw, unit_hint)
    if not price:
        return
    key = (crop, region)
    if key in seen:
        return
    seen.add(key)
    results.append(_make_item(crop, price, region, source, url))


# ── BachHoaXanh (/rau-cu-qua, /trai-cay) ──────────────────────────────────────
def _parse_bachhoaxanh(html: str, default_region: str, source: str) -> List[Dict]:
    """
    BachHoaXanh hiển thị sản phẩm trong các block có dạng:
      <div class="...product...">
        <h3 ...>Tên sản phẩm</h3>
        <strong ...>XX.XXX<sup>đ</sup>/100g</strong>
      </div>
    Giá thường là /100g hoặc /kg — cần chuẩn hóa về /kg.
    """
    results = []
    seen = set()
    source_url = "https://www.bachhoaxanh.com"

    # Tách từng block sản phẩm (thẻ <div> chứa cả tên lẫn giá)
    blocks = re.findall(
        r'<(?:div|li|article)[^>]*class="[^"]*(?:product|item|cate-pro)[^"]*"[^>]*>(.*?)</(?:div|li|article)>',
        html, re.DOTALL | re.IGNORECASE
    )
    if not blocks:
        # Fallback: lấy toàn bộ text và tìm pattern tên + giá liền nhau
        blocks = [html]

    for block in blocks:
        text = _strip_tags(block)
        text = re.sub(r"\s+", " ", text).strip()

        # Tìm giá: dạng "XX.XXX đ" hoặc "XX.XXXđ/100g"
        price_match = re.search(
            r"([\d]{1,3}(?:[.,]\d{3})+|\d{4,7})\s*(?:đ|vnđ|VND)?[\s/]*(100\s*g|200\s*g|500\s*g|kg)?",
            text, re.IGNORECASE
        )
        if not price_match:
            continue

        price_str = price_match.group(1)
        unit = price_match.group(2) or "kg"

        # Tìm tên sản phẩm (thường là text đầu tiên trong block)
        name_match = re.search(r"^([^\d]{3,50})", text.strip())
        if not name_match:
            continue
        name_raw = name_match.group(1).strip()

        _extract_and_add(name_raw, price_str, default_region, source, results, seen,
                         unit_hint=unit, url=source_url)

    # Nếu không parse được qua block → thử parse theo bảng HTML
    if not results:
        for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(1), re.DOTALL | re.IGNORECASE)
            if len(cells) < 2:
                continue
            _extract_and_add(_strip_tags(cells[0]), _strip_tags(cells[1]),
                              default_region, source, results, seen, url=source_url)

    return results


# ── WinMart (/danh-muc/rau-cu-qua) ────────────────────────────────────────────
def _parse_winmart(html: str, default_region: str, source: str) -> List[Dict]:
    """
    WinMart có cấu trúc tương tự BachHoaXanh: product cards với tên và giá.
    """
    results = []
    seen = set()
    source_url = "https://winmart.vn"

    blocks = re.findall(
        r'<(?:div|li|article)[^>]*class="[^"]*(?:product|item|card)[^"]*"[^>]*>(.*?)</(?:div|li|article)>',
        html, re.DOTALL | re.IGNORECASE
    )
    if not blocks:
        blocks = [html]

    for block in blocks:
        text = re.sub(r"\s+", " ", _strip_tags(block)).strip()
        price_match = re.search(
            r"([\d]{1,3}(?:[.,]\d{3})+|\d{4,7})\s*(?:đ|vnđ|VND)?[\s/]*(100\s*g|200\s*g|500\s*g|kg)?",
            text, re.IGNORECASE
        )
        if not price_match:
            continue
        price_str = price_match.group(1)
        unit = price_match.group(2) or "kg"
        name_match = re.search(r"^([^\d]{3,50})", text.strip())
        if not name_match:
            continue
        _extract_and_add(name_match.group(1).strip(), price_str, default_region, source,
                         results, seen, unit_hint=unit, url=source_url)

    if not results:
        for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE):
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(1), re.DOTALL | re.IGNORECASE)
            if len(cells) < 2:
                continue
            _extract_and_add(_strip_tags(cells[0]), _strip_tags(cells[1]),
                              default_region, source, results, seen, url=source_url)

    return results


# ── giacaphe.com ───────────────────────────────────────────────────────────────
def _parse_giacaphe(html: str, default_region: str, source: str) -> List[Dict]:
    results, seen = [], set()
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.DOTALL | re.IGNORECASE)
        if len(cells) < 2:
            continue
        region = _normalize_region(_strip_tags(cells[0])) or default_region
        _extract_and_add("Cà phê", _strip_tags(cells[1]), region, source, results, seen,
                         url="https://giacaphe.com")
    return results


# ── giatieu.com ────────────────────────────────────────────────────────────────
def _parse_giatieu(html: str, default_region: str, source: str) -> List[Dict]:
    results, seen = [], set()
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.DOTALL | re.IGNORECASE)
        if len(cells) < 2:
            continue
        region = _normalize_region(_strip_tags(cells[0])) or default_region
        _extract_and_add("Hồ tiêu", _strip_tags(cells[1]), region, source, results, seen,
                         url="https://giatieu.com")
    return results


# ── nongnghiep.vn ──────────────────────────────────────────────────────────────
def _parse_nongnghiep(html: str, default_region: str, source: str) -> List[Dict]:
    results, seen = [], set()
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", m.group(1), re.DOTALL | re.IGNORECASE)
        if len(cells) < 2:
            continue
        name_raw = _strip_tags(cells[0]).strip()
        price_raw = _strip_tags(cells[1]).strip()
        region = default_region
        if len(cells) >= 3:
            r = _normalize_region(_strip_tags(cells[2]))
            if r:
                region = r
        _extract_and_add(name_raw, price_raw, region, source, results, seen,
                         url="https://nongnghiep.vn")
    return results


# ── gia.vn ─────────────────────────────────────────────────────────────────────
def _parse_giavn(html: str, default_region: str, source: str) -> List[Dict]:
    results, seen = [], set()
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL | re.IGNORECASE):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.DOTALL | re.IGNORECASE)
        if len(cells) < 2:
            continue
        name_raw = _strip_tags(cells[0]).strip()
        price_raw = _strip_tags(cells[1]).strip()
        region = default_region
        if len(cells) >= 3:
            r = _normalize_region(_strip_tags(cells[2]))
            if r:
                region = r
        _extract_and_add(name_raw, price_raw, region, source, results, seen,
                         url="https://gia.vn")
    if not results:
        for m in re.finditer(
            r"([^\n\r<>]{3,40})[:\-–]\s*([\d][0-9.,\s]{2,12})(?:đ|VND|vnđ)?[\s/]?kg",
            _strip_tags(html), re.IGNORECASE,
        ):
            _extract_and_add(m.group(1), m.group(2), default_region, source, results, seen)
    return results


# ── Parser chung (fallback cho các trang mới) ──────────────────────────────────
def _parse_universal(html: str, default_region: str, source: str) -> List[Dict]:
    results, seen = [], set()
    text = _strip_tags(html)
    for alias in _CROP_ALIAS:
        pattern = re.compile(
            re.escape(alias) + r".{0,150}?([\d][0-9.,]{2,10})\s*(?:đ|VND|vnđ|đồng|nghìn|k\b)?",
            re.IGNORECASE | re.DOTALL,
        )
        for m in pattern.finditer(text):
            canonical = _CROP_ALIAS[alias]
            price = _parse_price_str(m.group(1))
            if price and _validate_price(price, canonical):
                key = (canonical, default_region)
                if key not in seen:
                    seen.add(key)
                    results.append(_make_item(canonical, price, default_region, source))
    return results


# ─── Danh sách nguồn (url, region_mặc_định, tên_nguồn, parser) ───────────────
_SOURCES = [
    # Ưu tiên 1: Siêu thị bán lẻ
    ("https://www.bachhoaxanh.com/rau-cu-qua",              "TP.HCM",  "bachhoaxanh.com", _parse_bachhoaxanh),
    ("https://www.bachhoaxanh.com/trai-cay",                "TP.HCM",  "bachhoaxanh.com", _parse_bachhoaxanh),
    ("https://winmart.vn/danh-muc/rau-cu-qua",              "Hà Nội",  "winmart.vn",      _parse_winmart),
    ("https://winmart.vn/danh-muc/trai-cay",                "Hà Nội",  "winmart.vn",      _parse_winmart),
    # Ưu tiên 2: Chuyên ngành
    ("https://giacaphe.com/gia-ca-phe-noi-dia/",            "Đắk Lắk", "giacaphe.com",    _parse_giacaphe),
    ("https://giatieu.com/gia-tieu-hom-nay/",               "Gia Lai", "giatieu.com",     _parse_giatieu),
    # Ưu tiên 3: Tin tức nông nghiệp
    ("https://nongnghiep.vn/gia-nong-san/",                 "TP.HCM",  "nongnghiep.vn",   _parse_nongnghiep),
    ("https://gia.vn/gia-nong-san/",                        "TP.HCM",  "gia.vn",          _parse_giavn),
    # Ưu tiên 4: Tổng hợp
    ("https://www.vigen.net.vn/gia-ca-nong-san",            "Hà Nội",  "vigen.net.vn",    _parse_universal),
    ("https://cadulo.com/gia-nong-san-hom-nay",             "TP.HCM",  "cadulo.com",      _parse_universal),
]


def _parse_tavily_raw(tavily_items: List[Dict]) -> List[Dict]:
    """
    Chuyển đổi raw items từ Tavily (crop_name_raw + price_raw)
    sang định dạng chuẩn (crop_name canonical + price_per_kg float).
    """
    results = []
    today = date.today().isoformat()
    for item in tavily_items:
        raw_name = item.get("crop_name_raw", "").strip().lower()
        raw_price = item.get("price_raw", "").strip()
        region = item.get("region", "TP.HCM")
        url = item.get("url", "")

        canonical = _CROP_ALIAS.get(raw_name)
        if not canonical:
            # Thử tìm alias chứa raw_name
            for alias, name in _CROP_ALIAS.items():
                if alias in raw_name or raw_name in alias:
                    canonical = name
                    break
        if not canonical:
            continue

        price = _parse_price_str(raw_price)
        if not price:
            continue

        results.append({
            "crop_name":   canonical,
            "region":      _normalize_region(region) or region,
            "price_per_kg": price,
            "source":      "tavily.com",
            "date":        today,
            "url":         url,
        })
    return results


async def _scrape_tavily() -> List[Dict]:
    """Cào giá từ Tavily Search (chạy trong thread pool vì SDK đồng bộ)."""
    try:
        from app.integrations.tavily_client import search_prices
        raw = await asyncio.to_thread(search_prices, 4)
        parsed = _parse_tavily_raw(raw)
        logger.info(f"[Tavily] Cào được {len(raw)} raw → {len(parsed)} hợp lệ")
        return parsed
    except Exception as e:
        logger.debug(f"[Tavily] Bỏ qua: {e}")
        return []


async def _scrape_web() -> List[Dict]:
    """Cào từ tất cả nguồn (httpx parsers + Tavily). Trả về raw items (chưa filter)."""
    raw: List[Dict] = []

    # ── Nguồn httpx truyền thống ────────────────────────────────────────────
    async with httpx.AsyncClient(
        timeout=20,
        follow_redirects=True,
        headers=_HTTP_HEADERS,
    ) as client:
        for url, default_region, source_name, parser_fn in _SOURCES:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    # Ép UTF-8 để tránh lỗi encoding trên Windows (cp1252 garble tiếng Việt)
                    content = resp.content
                    try:
                        html = content.decode("utf-8")
                        if "" in html:
                            raise UnicodeError("utf-8 produced replacement characters")
                    except Exception:
                        try:
                            html = content.decode("cp1252")
                        except Exception:
                            html = content.decode("latin1", errors="replace")

                    items = parser_fn(html, default_region=default_region, source=source_name)
                    raw.extend(items)
                    logger.info(f"[Crawler] {source_name} ({url}): {len(items)} mục raw")
                else:
                    logger.debug(f"[Crawler] {source_name}: HTTP {resp.status_code}")
            except Exception as e:
                logger.debug(f"[Crawler] {source_name} lỗi: {type(e).__name__}: {e}")

    # ── Tavily Search (chạy song song với httpx) ────────────────────────────
    tavily_items = await _scrape_tavily()
    raw.extend(tavily_items)

    return raw


# ─── Giả lập (fallback) ───────────────────────────────────────────────────────
# Theo spec anti-timeout + no-mock:
# Không được sinh/insert dữ liệu mô phỏng cho giá. Các hàm này hiện chỉ được giữ lại
# để không phá cấu trúc cũ, nhưng KHÔNG được gọi trong pipeline background nữa.
def _generate_simulation_prices() -> List[Dict]:
    raise RuntimeError("Simulation prices are disabled by spec (no-mock).")


def _generate_historical_prices(
    days: int = 7,
    reference: Optional[List[Dict]] = None,
) -> List[Dict]:
    raise RuntimeError("Synthetic historical prices are disabled by spec (no-mock).")


# ─── DB helpers ───────────────────────────────────────────────────────────────

def _save_market_prices(items: List[Dict]) -> int:
    """
    Upsert danh sách giá đã được pre-filter vào bảng MarketPrices.
    Khi cùng crop+region+date đã có: chỉ ghi đè nếu nguồn mới có priority cao hơn.
    """
    if not items:
        return 0

    from app.core.database import SessionLocal
    from app.models.crop import CropType
    from app.models.price import MarketPrice

    db = SessionLocal()
    saved = 0
    today = date.today()
    _crop_cache: Dict[str, object] = {}

    def _find_crop(name: str):
        if name in _crop_cache:
            return _crop_cache[name]
        crop = (
            db.query(CropType).filter(CropType.CropName == name).first()
            or db.query(CropType).filter(CropType.CropName.ilike(name)).first()
            or db.query(CropType).filter(CropType.CropName.ilike(f"%{name}%")).first()
        )
        _crop_cache[name] = crop
        return crop

    try:
        for item in items:
            crop_name = str(item.get("crop_name", "")).strip()
            region = str(item.get("region", "")).strip()
            price = float(item.get("price_per_kg", 0))
            source = str(item.get("source", "auto_crawler"))
            source_url = str(item.get("url", ""))

            if not crop_name or not region or price <= 0:
                continue

            crop = _find_crop(crop_name)
            if not crop:
                logger.debug(f"[Save] Bỏ qua '{crop_name}' — không có trong DB CropTypes")
                continue

            try:
                price_date = date.fromisoformat(item.get("date") or today.isoformat())
            except (ValueError, TypeError):
                price_date = today

            existing = (
                db.query(MarketPrice)
                .filter(
                    MarketPrice.CropID == crop.CropID,
                    MarketPrice.Region == region,
                    MarketPrice.PriceDate == price_date,
                )
                .first()
            )

            new_priority = SOURCE_PRIORITY.get(source, 50)
            if existing:
                existing_priority = SOURCE_PRIORITY.get(existing.SourceName or "", 50)
                # Chỉ ghi đè nếu nguồn mới có uy tín bằng hoặc cao hơn
                if new_priority <= existing_priority:
                    existing.PricePerKg = price
                    existing.SourceName = source
                    existing.SourceURL = source_url
            else:
                db.add(MarketPrice(
                    CropID=crop.CropID,
                    Region=region,
                    PricePerKg=price,
                    SourceName=source,
                    SourceURL=source_url,
                    PriceDate=price_date,
                ))
            saved += 1

        db.commit()
    except Exception as e:
        logger.error(f"[Save] Lỗi lưu MarketPrices: {e}")
        db.rollback()
    finally:
        db.close()

    return saved


def _save_market_prices_force(items: List[Dict]) -> int:
    """
    Ghi đè TOÀN BỘ — luôn cập nhật giá mới nhất bất kể nguồn cũ.
    Dùng khi seed lịch sử 7 ngày lúc khởi động.
    """
    if not items:
        return 0

    from app.core.database import SessionLocal
    from app.models.crop import CropType
    from app.models.price import MarketPrice

    db = SessionLocal()
    saved = 0
    today = date.today()
    _crop_cache: Dict[str, object] = {}

    def _find_crop(name: str):
        if name in _crop_cache:
            return _crop_cache[name]
        crop = (
            db.query(CropType).filter(CropType.CropName == name).first()
            or db.query(CropType).filter(CropType.CropName.ilike(name)).first()
            or db.query(CropType).filter(CropType.CropName.ilike(f"%{name}%")).first()
        )
        _crop_cache[name] = crop
        return crop

    try:
        for item in items:
            crop_name = str(item.get("crop_name", "")).strip()
            region    = str(item.get("region", "")).strip()
            source    = str(item.get("source", "web_crawler"))
            source_url = str(item.get("url", ""))
            try:
                price = float(item.get("price_per_kg", 0))
            except (TypeError, ValueError):
                continue
            if not crop_name or not region or price <= 0:
                continue

            crop = _find_crop(crop_name)
            if not crop:
                continue

            try:
                price_date = date.fromisoformat(str(item.get("date") or today.isoformat()))
            except (ValueError, TypeError):
                price_date = today

            existing = (
                db.query(MarketPrice)
                .filter(
                    MarketPrice.CropID == crop.CropID,
                    MarketPrice.Region == region,
                    MarketPrice.PriceDate == price_date,
                )
                .first()
            )
            if existing:
                existing.PricePerKg = price
                existing.SourceName = source
                existing.SourceURL  = source_url
                existing.SourceType = "web_crawler"
                existing.ObservedAt = datetime.now()
                existing.FetchedAt = datetime.now()
                existing.IsRealtime = True
                existing.IsMock = False
            else:
                db.add(MarketPrice(
                    CropID=crop.CropID,
                    Region=region,
                    PricePerKg=price,
                    SourceName=source,
                    SourceURL=source_url,
                    SourceType="web_crawler",
                    ObservedAt=datetime.now(),
                    FetchedAt=datetime.now(),
                    IsRealtime=True,
                    IsMock=False,
                    PriceDate=price_date,
                ))
            saved += 1

        db.commit()
        logger.info(f"[SaveForce] Đã ghi đè {saved} bản ghi vào MarketPrices")
    except Exception as e:
        logger.error(f"[SaveForce] Lỗi: {e}")
        db.rollback()
    finally:
        db.close()
    return saved


def _aggregate_history_range(days: int = 7) -> int:
    """
    Tổng hợp MarketPrices của N ngày gần nhất → PriceHistory (avg/min/max).
    Ghi đè PriceHistory cũ nếu đã tồn tại.
    """
    from datetime import timedelta
    from app.core.database import SessionLocal
    from app.models.price import MarketPrice, PriceHistory
    from sqlalchemy import func

    db = SessionLocal()
    updated = 0
    today = date.today()
    since = today - timedelta(days=days - 1)

    try:
        rows = (
            db.query(
                MarketPrice.CropID,
                MarketPrice.Region,
                MarketPrice.PriceDate,
                func.avg(MarketPrice.PricePerKg).label("avg"),
                func.min(MarketPrice.PricePerKg).label("mn"),
                func.max(MarketPrice.PricePerKg).label("mx"),
                func.count().label("vol"),
            )
            .filter(MarketPrice.PriceDate >= since)
            .group_by(MarketPrice.CropID, MarketPrice.Region, MarketPrice.PriceDate)
            .all()
        )

        for row in rows:
            existing = (
                db.query(PriceHistory)
                .filter(
                    PriceHistory.CropID == row.CropID,
                    PriceHistory.Region == row.Region,
                    PriceHistory.RecordDate == row.PriceDate,
                )
                .first()
            )
            if existing:
                existing.AvgPrice = row.avg
                existing.MinPrice = row.mn
                existing.MaxPrice = row.mx
                existing.Volume   = float(row.vol)
            else:
                db.add(PriceHistory(
                    CropID=row.CropID,
                    Region=row.Region,
                    AvgPrice=row.avg,
                    MinPrice=row.mn,
                    MaxPrice=row.mx,
                    Volume=float(row.vol),
                    RecordDate=row.PriceDate,
                ))
            updated += 1

        db.commit()
        logger.info(f"[AggRange] Tổng hợp {updated} bản ghi PriceHistory ({days} ngày)")
    except Exception as e:
        logger.error(f"[AggRange] Lỗi: {e}")
        db.rollback()
    finally:
        db.close()
    return updated


def _aggregate_to_price_history() -> int:
    from app.core.database import SessionLocal
    from app.models.price import MarketPrice, PriceHistory
    from sqlalchemy import func

    db = SessionLocal()
    updated = 0
    today = date.today()
    try:
        rows = (
            db.query(
                MarketPrice.CropID,
                MarketPrice.Region,
                func.avg(MarketPrice.PricePerKg).label("avg"),
                func.min(MarketPrice.PricePerKg).label("mn"),
                func.max(MarketPrice.PricePerKg).label("mx"),
                func.count().label("vol"),
            )
            .filter(MarketPrice.PriceDate == today)
            .group_by(MarketPrice.CropID, MarketPrice.Region)
            .all()
        )
        for row in rows:
            existing = (
                db.query(PriceHistory)
                .filter(
                    PriceHistory.CropID == row.CropID,
                    PriceHistory.Region == row.Region,
                    PriceHistory.RecordDate == today,
                )
                .first()
            )
            if existing:
                existing.AvgPrice = row.avg
                existing.MinPrice = row.mn
                existing.MaxPrice = row.mx
                existing.Volume = float(row.vol)
            else:
                db.add(PriceHistory(
                    CropID=row.CropID, Region=row.Region,
                    AvgPrice=row.avg, MinPrice=row.mn,
                    MaxPrice=row.mx, Volume=float(row.vol),
                    RecordDate=today,
                ))
            updated += 1
        db.commit()
    except Exception as e:
        logger.error(f"[Aggregate] Lỗi: {e}")
        db.rollback()
    finally:
        db.close()
    return updated


def _check_and_trigger_alerts() -> int:
    from app.core.database import SessionLocal
    from app.models.price import MarketPrice
    from app.models.alert import PriceAlert as AlertSubscription
    from app.models.crop import CropType
    from app.models.user import User

    db = SessionLocal()
    alerts_sent = 0
    try:
        subscriptions = db.query(AlertSubscription).filter(AlertSubscription.IsActive == True).all()
        for sub in subscriptions:
            latest = (
                db.query(MarketPrice)
                .filter(MarketPrice.CropID == sub.CropID, MarketPrice.Region == sub.Region)
                .order_by(MarketPrice.PriceDate.desc())
                .first()
            )
            if latest and sub.TargetPrice <= latest.PricePerKg:
                crop = db.query(CropType).filter(CropType.CropID == sub.CropID).first()
                user = db.query(User).filter(User.UserID == sub.UserID).first()
                if user:
                    subject, plain, html = notification_service.build_price_alert_message(
                        crop_name=crop.CropName if crop else "Nông sản",
                        region=sub.Region,
                        current_price=float(latest.PricePerKg),
                        target_price=float(sub.TargetPrice),
                        condition=">=",
                    )
                    notification_service.send("email", user.Email or "nongdan@example.com", subject, plain, html)
                alerts_sent += 1
    except Exception as e:
        logger.error(f"[Alert] Lỗi kiểm tra: {e}")
    finally:
        db.close()
    return alerts_sent


# ─── Public API ───────────────────────────────────────────────────────────────

async def run_price_crawler() -> Dict:
    """
    Pipeline (anti-timeout + no-mock):
    - Chỉ lưu dữ liệu nếu crawl được dữ liệu thật và pass prefilter.
    - Nếu không có dữ liệu thật: KHÔNG sinh/simulation; trả saved=0 để frontend nhận cache miss.
    """
    t0 = datetime.now()

    raw_items = await _scrape_web()
    filtered = prefilter_items(raw_items)

    source_tag = "web"
    if not filtered:
        logger.warning("[Crawler] Không crawl được dữ liệu giá thật hợp lệ — bỏ qua insert (no-mock).")
        elapsed = round((datetime.now() - t0).total_seconds(), 2)
        return {
            "raw_count": len(raw_items),
            "filtered_count": 0,
            "saved": 0,
            "aggregated": 0,
            "alerts": 0,
            "weather_saved": 0,
            "source": source_tag,
            "elapsed_s": elapsed,
        }

    saved = await asyncio.to_thread(_save_market_prices, filtered)
    aggregated = await asyncio.to_thread(_aggregate_to_price_history)
    alerts = await asyncio.to_thread(_check_and_trigger_alerts)

    # Cập nhật thời tiết (Open-Meteo) trong background: không block request trang.
    weather_rows = await _fetch_all_weather(past_days=0, forecast_days=7)
    weather_saved = await asyncio.to_thread(_save_weather_data_force, weather_rows)

    elapsed = round((datetime.now() - t0).total_seconds(), 2)
    logger.info(
        f"[Crawler] ✓ raw={len(raw_items)} filtered={len(filtered)} saved={saved} "
        f"history={aggregated} alerts={alerts} weather={weather_saved} source={source_tag} | {elapsed}s"
    )
    return {
        "raw_count": len(raw_items),
        "filtered_count": len(filtered),
        "saved": saved,
        "aggregated": aggregated,
        "alerts": alerts,
        "weather_saved": weather_saved,
        "source": source_tag,
        "elapsed_s": elapsed,
    }


# ─── WeatherData crawler (Open-Meteo, free, no API key) ──────────────────────

_WEATHER_PROVINCES = [
    ("TP.HCM",     10.8231, 106.6297),
    ("Hà Nội",     21.0285, 105.8542),
    ("Đà Nẵng",    16.0544, 108.2022),
    ("Cần Thơ",    10.0452, 105.7469),
    ("Đắk Lắk",   12.6667, 108.0500),
    ("Lâm Đồng",  11.9465, 108.4419),
    ("Gia Lai",    13.9833, 108.0000),
    ("Tiền Giang", 10.3600, 106.3600),
    ("Long An",    10.5400, 106.4100),
    ("Bình Thuận", 10.9280, 108.1000),
]

_WEATHER_CODES: Dict[int, str] = {
    0: "Trời quang", 1: "Phần lớn quang", 2: "Có mây rải rác", 3: "Nhiều mây",
    45: "Sương mù", 48: "Sương mù băng giá",
    51: "Mưa phùn nhẹ", 53: "Mưa phùn vừa", 55: "Mưa phùn dày",
    61: "Mưa nhỏ", 63: "Mưa vừa", 65: "Mưa to",
    71: "Tuyết nhẹ", 73: "Tuyết vừa", 75: "Tuyết to",
    80: "Mưa rào nhẹ", 81: "Mưa rào vừa", 82: "Mưa rào to",
    95: "Giông bão", 96: "Giông có mưa đá nhỏ", 99: "Giông có mưa đá lớn",
}


async def _fetch_weather_province(
    client: "httpx.AsyncClient",
    region: str,
    lat: float,
    lon: float,
    past_days: int = 6,
    forecast_days: int = 7,
) -> List[Dict]:
    """Gọi Open-Meteo cho một tỉnh. Trả về past_days+forecast_days bản ghi (1/ngày).
    Mặc định: 6 ngày quá khứ + hôm nay + 6 ngày tương lai = 13 ngày.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f",relative_humidity_2m_max,sunshine_duration,weather_code"
        f",wind_speed_10m_max,uv_index_max"
        f"&timezone=Asia%2FHo_Chi_Minh"
        f"&past_days={past_days}"
        f"&forecast_days={forecast_days}"
    )
    try:
        resp = await client.get(url, timeout=8)
        if resp.status_code == 429:
            logger.warning(f"[Weather] {region}: Rate limited (429) — sẽ retry")
            return []
        if resp.status_code != 200:
            logger.debug(f"[Weather] {region}: HTTP {resp.status_code}")
            return []
        data = resp.json()
        daily = data.get("daily", {})
        dates       = daily.get("time", [])
        tmax        = daily.get("temperature_2m_max", [])
        tmin        = daily.get("temperature_2m_min", [])
        rain        = daily.get("precipitation_sum", [])
        humidity    = daily.get("relative_humidity_2m_max", [])
        sunshine    = daily.get("sunshine_duration", [])   # seconds
        codes       = daily.get("weather_code", [])
        wind_speeds = daily.get("wind_speed_10m_max", [])
        uv_indices  = daily.get("uv_index_max", [])

        def _get(lst, idx):
            v = lst[idx] if idx < len(lst) else None
            return float(v) if v is not None else None

        results = []
        for i, d in enumerate(dates):
            wcode = int(codes[i]) if i < len(codes) and codes[i] is not None else 0
            desc  = _WEATHER_CODES.get(wcode, "Không xác định")
            sun_s = _get(sunshine, i)
            sun_h = round(sun_s / 3600, 1) if sun_s is not None else None

            results.append({
                "region":       region,
                "date":         d,
                "temp_min":     _get(tmin, i),
                "temp_max":     _get(tmax, i),
                "humidity":     _get(humidity, i),
                "rainfall":     _get(rain, i),
                "sunshine_h":   sun_h,
                "weather_desc": desc,
                "weather_code": wcode,
                "wind_speed":   _get(wind_speeds, i),
                "uv_index":     _get(uv_indices, i),
                "latitude":     lat,
                "longitude":    lon,
            })
        logger.info(f"[Weather] {region}: {len(results)} ngày")
        return results
    except Exception as e:
        logger.debug(f"[Weather] {region} lỗi: {e}")
        return []


async def _fetch_all_weather(past_days: int = 6, forecast_days: int = 7) -> List[Dict]:
    """Cào thời tiết song song cho tất cả tỉnh, giới hạn 3 request đồng thời tránh 429."""
    semaphore = asyncio.Semaphore(3)

    async def _fetch_with_limit(client, region, lat, lon):
        async with semaphore:
            for attempt in range(2):
                rows = await _fetch_weather_province(client, region, lat, lon, past_days, forecast_days)
                if rows:
                    return rows
                # 429 hoặc lỗi tạm thời — chờ rồi retry
                await asyncio.sleep(1.5 * (attempt + 1))
            return []

    async with httpx.AsyncClient() as client:
        tasks = [
            _fetch_with_limit(client, region, lat, lon)
            for region, lat, lon in _WEATHER_PROVINCES
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_rows = []
    for r in results:
        if isinstance(r, list):
            all_rows.extend(r)
    return all_rows


def _save_weather_data_force(rows: List[Dict]) -> int:
    """Upsert (ghi đè) WeatherData — 1 bản ghi / tỉnh / ngày."""
    if not rows:
        return 0

    from app.core.database import SessionLocal
    from app.models.weather import WeatherData

    db = SessionLocal()
    saved = 0
    fetched_at = datetime.now()
    try:
        for row in rows:
            region = str(row.get("region", "")).strip()
            date_str = str(row.get("date", "")).strip()
            if not region or not date_str:
                continue
            try:
                record_date = date.fromisoformat(date_str)
            except ValueError:
                continue

            existing = (
                db.query(WeatherData)
                .filter(WeatherData.Region == region, WeatherData.RecordDate == record_date)
                .first()
            )
            if existing:
                existing.TempMin        = row.get("temp_min")
                existing.TempMax        = row.get("temp_max")
                existing.Humidity       = row.get("humidity")
                existing.Rainfall       = row.get("rainfall")
                existing.SunshineHours  = row.get("sunshine_h")
                existing.WeatherDesc    = row.get("weather_desc")
                existing.WeatherCode    = row.get("weather_code")
                existing.WindSpeed      = row.get("wind_speed")
                existing.UVIndex        = row.get("uv_index")
                existing.Latitude       = row.get("latitude")
                existing.Longitude      = row.get("longitude")
                existing.SourceName     = "Open-Meteo"
                existing.SourceURL      = "https://api.open-meteo.com/v1/forecast"
                # Hàng của hôm nay có thể đang giữ số đo realtime cùng mốc quan
                # trắc thật. Crawler dự báo chạy mỗi vài phút; ghi đè mốc đó sẽ
                # khiến số đo cũ được báo là "vừa cập nhật".
                if existing.Temperature is None:
                    existing.SourceUpdatedAt = fetched_at
                existing.FetchedAt      = fetched_at
                existing.IsRealtime     = True
                existing.IsMock         = False
            else:
                db.add(WeatherData(
                    Region=region,
                    RecordDate=record_date,
                    TempMin=row.get("temp_min"),
                    TempMax=row.get("temp_max"),
                    Humidity=row.get("humidity"),
                    Rainfall=row.get("rainfall"),
                    SunshineHours=row.get("sunshine_h"),
                    WeatherDesc=row.get("weather_desc"),
                    WeatherCode=row.get("weather_code"),
                    WindSpeed=row.get("wind_speed"),
                    UVIndex=row.get("uv_index"),
                    Latitude=row.get("latitude"),
                    Longitude=row.get("longitude"),
                    SourceName="Open-Meteo",
                    SourceURL="https://api.open-meteo.com/v1/forecast",
                    SourceUpdatedAt=fetched_at,
                    FetchedAt=fetched_at,
                    IsRealtime=True,
                    IsMock=False,
                ))
            saved += 1

        db.commit()
        logger.info(f"[Weather] Lưu {saved} bản ghi WeatherData")
    except Exception as e:
        logger.error(f"[Weather] Lỗi lưu: {e}")
        db.rollback()
    finally:
        db.close()
    return saved


async def seed_7_days_on_startup() -> Dict:
    """
    Theo spec no-mock:
    - Không seed/sinh thêm dữ liệu giá lịch sử.
    - Startup chỉ khởi động nền crawler theo interval để có dữ liệu thật từ crawl/API.
    """
    logger.info("[Startup] seed_7_days_on_startup() disabled by spec (no-mock).")
    return {"disabled": True}


async def auto_crawl_loop():
    """
    Background loop (anti-timeout + no-mock):
    - Không seed/sinh lịch sử khi startup.
    - Chỉ chạy run_price_crawler theo interval để cập nhật dữ liệu thật.
    """
    logger.info(f"[Crawler] Khởi động, interval={CRAWL_INTERVAL}s")
    await asyncio.sleep(int(os.getenv("CRAWL_STARTUP_DELAY_SECONDS", "60")))

    # Chạy ngay lần đầu để tạo cache thật nếu crawl được, nhưng không seed giả.
    try:
        await run_price_crawler()
    except Exception as e:
        logger.error(f"[Crawler] Lỗi run_price_crawler lần đầu: {e}")

    while True:
        try:
            await asyncio.sleep(CRAWL_INTERVAL)
            await run_price_crawler()
        except asyncio.CancelledError:
            logger.info("[Crawler] Đã dừng.")
            break
        except Exception as e:
            logger.error(f"[Crawler] Lỗi vòng lặp: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# Cào thời tiết thời gian thực
# ═══════════════════════════════════════════════════════════════════════════
#
# Trước đây thời tiết chỉ được làm mới như tác dụng phụ của run_price_crawler:
# cào giá hỏng là hàm return sớm, thời tiết đứng theo. Cộng với việc Beat chưa
# từng chạy, bảng WeatherData chỉ được cập nhật khi có người mở trang và cache
# đã quá hạn — nghĩa là chính request của người dùng phải chờ Open-Meteo trả
# lời. Đó là nguồn gốc của thông báo "Dữ liệu realtime đang chậm (timeout)".
#
# Task dưới đây chạy độc lập theo lịch, đẩy việc chờ mạng ra khỏi request.

from app.integrations.weather_client import WeatherClient  # noqa: E402
from app.tasks.celery_app import celery_app  # noqa: E402
from app.repositories.weather_repository import upsert_weather_cache  # noqa: E402

_weather_client_realtime = WeatherClient()


def _vung_can_cao() -> List[str]:
    """Danh sách vùng, đã gộp bí danh trùng toạ độ.

    REGION_COORDINATES_JSON khai báo cả "Ha Noi" lẫn "Hà Nội" trỏ cùng một
    điểm. Cào cả hai là gọi Open-Meteo gấp đôi cho cùng một số liệu; giữ tên
    có dấu vì _normalize_region quy mọi biến thể về đó trước khi tra DB.
    """
    import json

    from app.core.config import settings

    try:
        cau_hinh = json.loads(settings.REGION_COORDINATES_JSON or "{}")
    except json.JSONDecodeError:
        logger.error("[Weather] REGION_COORDINATES_JSON hỏng — không cào được vùng nào")
        return []

    theo_toa_do: Dict[Tuple[float, float], str] = {}
    for ten, toa_do in cau_hinh.items():
        try:
            khoa = (round(float(toa_do["latitude"]), 4), round(float(toa_do["longitude"]), 4))
        except (KeyError, TypeError, ValueError):
            continue
        cu = theo_toa_do.get(khoa)
        # Ưu tiên tên có dấu: đó là dạng chuẩn mà _normalize_region trả về.
        if cu is None or (not _co_dau(cu) and _co_dau(ten)):
            theo_toa_do[khoa] = ten
    return list(theo_toa_do.values())


def _co_dau(text: str) -> bool:
    return any(ord(ky_tu) > 127 for ky_tu in text)


def crawl_weather_realtime() -> Dict:
    """Cào quan trắc hiện tại cho mọi vùng, ghi thẳng vào cache.

    Một vùng lỗi mạng không được kéo theo các vùng còn lại — nông dân ở Lâm
    Đồng không nên mất dữ liệu chỉ vì Cần Thơ timeout.
    """
    from app.core.database import SessionLocal

    t0 = datetime.now()
    vung = _vung_can_cao()
    db = SessionLocal()
    saved = 0
    failed = 0
    try:
        for ten_vung in vung:
            try:
                live = _weather_client_realtime.get_current(ten_vung)
            except Exception as exc:
                failed += 1
                logger.warning(f"[Weather] {ten_vung}: {type(exc).__name__} — {exc}")
                continue

            if not live or live.get("temperature") is None:
                failed += 1
                logger.warning(f"[Weather] {ten_vung}: nguồn trả rỗng, bỏ qua (không bịa số)")
                continue

            upsert_weather_cache(
                db,
                region=ten_vung,
                record_date=date.today(),
                temperature=live.get("temperature"),
                temp_min=live.get("temp_min"),
                temp_max=live.get("temp_max"),
                rainfall=live.get("rainfall"),
                humidity=live.get("humidity"),
                condition=live.get("condition"),
                latitude=live.get("latitude"),
                longitude=live.get("longitude"),
                wind_speed=live.get("wind_speed"),
                uv_index=live.get("uv_index"),
                pressure=live.get("pressure"),
                weather_code=live.get("weather_code"),
                source_name=live.get("source_name") or "Open-Meteo",
                source_url=live.get("source_url"),
                source_updated_at=live.get("source_updated_at"),
                fetched_at=datetime.now(),
                is_realtime=True,
                is_mock=False,
            )
            saved += 1
    finally:
        db.close()

    elapsed = round((datetime.now() - t0).total_seconds(), 2)
    logger.info(f"[Weather] ✓ saved={saved} failed={failed} vùng={len(vung)} | {elapsed}s")
    return {"saved": saved, "failed": failed, "regions": len(vung), "elapsed_s": elapsed}


@celery_app.task(name="app.tasks.crawler_tasks.crawl_weather_realtime")
def crawl_weather_realtime_task() -> Dict:
    return crawl_weather_realtime()


@celery_app.task(name="app.tasks.crawler_tasks.run_price_crawler")
def run_price_crawler_task() -> Dict:
    """Cầu nối cho Beat: run_price_crawler là coroutine, Celery không await được."""
    return asyncio.run(run_price_crawler())
