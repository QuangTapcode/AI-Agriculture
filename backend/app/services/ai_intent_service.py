import re
import unicodedata


GREETING_REPLY = (
    "Chào bạn 👋 Mình là trợ lý AI nông nghiệp. Bạn muốn mình hỗ trợ về giá nông sản, "
    "thời tiết, mùa vụ, chất lượng hay cảnh báo rủi ro hôm nay?"
)

GENERAL_CAPABILITY_REPLY = (
    "Mình có thể hỗ trợ bạn theo 5 nhóm chính: phân tích giá nông sản, thời tiết canh tác, "
    "mùa vụ/thu hoạch, chất lượng nông sản và cảnh báo rủi ro. Bạn chỉ cần hỏi rõ nội dung, "
    "ví dụ: “giá cà chua ở Hà Nội hôm nay”, “hôm nay có nên tưới lúa không?” hoặc "
    "“mùa vụ của tôi khi nào thu hoạch?”."
)

ANALYSIS_INTENTS = {
    "price_analysis",
    "weather_analysis",
    "harvest_analysis",
    "quality_analysis",
    "alert_analysis",
    "full_farm_analysis",
}

INTENT_ALIASES = {
    "general": "general_question",
    "price": "price_analysis",
    "price_query": "price_analysis",
    "weather": "weather_analysis",
    "weather_advice": "weather_analysis",
    "harvest": "harvest_analysis",
    "harvest_advice": "harvest_analysis",
    "cultivation": "cultivation_advice",
    "quality": "quality_analysis",
    "quality_check": "quality_analysis",
    "alert": "alert_analysis",
    "alert_summary": "alert_analysis",
    "dashboard": "full_farm_analysis",
    "farm": "full_farm_analysis",
    "agriculture": "full_farm_analysis",
}

DB_TOPIC_BY_INTENT = {
    "price_analysis": "Gia ca",
    "price_query": "Gia ca",
    "price": "Gia ca",
    "weather_analysis": "Thoi tiet",
    "weather_advice": "Thoi tiet",
    "weather": "Thoi tiet",
    "harvest_analysis": "Thu hoach",
    "harvest_advice": "Thu hoach",
    "harvest": "Thu hoach",
    "cultivation_advice": "Ky thuat canh tac",
    "quality_analysis": "Chat luong",
    "quality_check": "Chat luong",
    "quality": "Chat luong",
    "pest": "Dich benh",
    "greeting": "Khac",
    "general_question": "Khac",
    "general": "Khac",
    "alert_analysis": "Khac",
    "alert_summary": "Khac",
    "full_farm_analysis": "Khac",
    "cultivation": "Ky thuat canh tac",
    "soil_salinity": "Khac",
    "soil_acidity": "Khac",
    "agriculture": "Khac",
}

REGION_KEYWORDS: dict[str, str] = {
    # ── Miền Bắc ─────────────────────────────────────────────────────────────
    "ha noi": "Hà Nội",
    "thu do": "Hà Nội",
    "hai phong": "Hải Phòng",
    "quang ninh": "Quảng Ninh",
    "ha long": "Quảng Ninh",
    "cam pha": "Quảng Ninh",
    "mong cai": "Quảng Ninh",
    "hai duong": "Hải Dương",
    "hung yen": "Hưng Yên",
    "thai binh": "Thái Bình",
    "nam dinh": "Nam Định",
    "ninh binh": "Ninh Bình",
    "ha nam": "Hà Nam",
    "vinh phuc": "Vĩnh Phúc",
    "phuc yen": "Vĩnh Phúc",
    "bac ninh": "Bắc Ninh",
    "bac giang": "Bắc Giang",
    "thai nguyen": "Thái Nguyên",
    "phu tho": "Phú Thọ",
    "viet tri": "Phú Thọ",
    "yen bai": "Yên Bái",
    "lao cai": "Lào Cai",
    "sa pa": "Lào Cai",
    "sapa": "Lào Cai",
    "ha giang": "Hà Giang",
    "tuyen quang": "Tuyên Quang",
    "cao bang": "Cao Bằng",
    "bac kan": "Bắc Kạn",
    "lang son": "Lạng Sơn",
    "son la": "Sơn La",
    "dien bien": "Điện Biên",
    "dien bien phu": "Điện Biên",
    "lai chau": "Lai Châu",
    "hoa binh": "Hòa Bình",
    "thanh hoa": "Thanh Hóa",
    "nghe an": "Nghệ An",
    "vinh": "Nghệ An",
    "ha tinh": "Hà Tĩnh",
    # ── Miền Trung ───────────────────────────────────────────────────────────
    "quang binh": "Quảng Bình",
    "dong hoi": "Quảng Bình",
    "le thuy": "Quảng Bình",
    "quang tri": "Quảng Trị",
    "dong ha": "Quảng Trị",
    "thua thien hue": "Thừa Thiên Huế",
    "thua thien": "Thừa Thiên Huế",
    "hue": "Thừa Thiên Huế",
    "da nang": "Đà Nẵng",
    "quang nam": "Quảng Nam",
    "hoi an": "Quảng Nam",
    "tam ky": "Quảng Nam",
    "quang ngai": "Quảng Ngãi",
    "binh dinh": "Bình Định",
    "quy nhon": "Bình Định",
    "phu yen": "Phú Yên",
    "tuy hoa": "Phú Yên",
    "khanh hoa": "Khánh Hòa",
    "nha trang": "Khánh Hòa",
    "cam ranh": "Khánh Hòa",
    "ninh thuan": "Ninh Thuận",
    "phan rang": "Ninh Thuận",
    "binh thuan": "Bình Thuận",
    "phan thiet": "Bình Thuận",
    "la gi": "Bình Thuận",
    # ── Tây Nguyên ──────────────────────────────────────────────────────────
    "kon tum": "Kon Tum",
    "gia lai": "Gia Lai",
    "pleiku": "Gia Lai",
    "an khe": "Gia Lai",
    "dak lak": "Đắk Lắk",
    "buon ma thuot": "Đắk Lắk",
    "buon ho": "Đắk Lắk",
    "dak nong": "Đắk Nông",
    "gia nghia": "Đắk Nông",
    "lam dong": "Lâm Đồng",
    "da lat": "Đà Lạt",
    "bao loc": "Lâm Đồng",
    # ── Đông Nam Bộ ─────────────────────────────────────────────────────────
    "ho chi minh": "TP.HCM",
    "tp hcm": "TP.HCM",
    "tphcm": "TP.HCM",
    "sai gon": "TP.HCM",
    "binh phuoc": "Bình Phước",
    "dong xoai": "Bình Phước",
    "binh duong": "Bình Dương",
    "thu dau mot": "Bình Dương",
    "dong nai": "Đồng Nai",
    "bien hoa": "Đồng Nai",
    "ba ria vung tau": "Bà Rịa - Vũng Tàu",
    "ba ria": "Bà Rịa - Vũng Tàu",
    "vung tau": "Bà Rịa - Vũng Tàu",
    "tay ninh": "Tây Ninh",
    # ── ĐBSCL ────────────────────────────────────────────────────────────────
    "long an": "Long An",
    "tan an": "Long An",
    "tien giang": "Tiền Giang",
    "my tho": "Tiền Giang",
    "go cong": "Tiền Giang",
    "ben tre": "Bến Tre",
    "tra vinh": "Trà Vinh",
    "vinh long": "Vĩnh Long",
    "dong thap": "Đồng Tháp",
    "cao lanh": "Đồng Tháp",
    "sa dec": "Đồng Tháp",
    "an giang": "An Giang",
    "long xuyen": "An Giang",
    "chau doc": "An Giang",
    "kien giang": "Kiên Giang",
    "rach gia": "Kiên Giang",
    "ha tien": "Kiên Giang",
    "phu quoc": "Kiên Giang",
    "can tho": "Cần Thơ",
    "hau giang": "Hậu Giang",
    "vi thanh": "Hậu Giang",
    "soc trang": "Sóc Trăng",
    "bac lieu": "Bạc Liêu",
    "ca mau": "Cà Mau",
    # ── Vùng / miền ─────────────────────────────────────────────────────────
    "mien bac": "Miền Bắc",
    "mien trung": "Miền Trung",
    "mien nam": "Miền Nam",
    "tay nguyen": "Tây Nguyên",
    "dong nam bo": "Đông Nam Bộ",
    "dbscl": "ĐBSCL",
    "mien tay": "ĐBSCL",
    "dong bang song cuu long": "ĐBSCL",
    "dbsh": "Đồng bằng sông Hồng",
    "dong bang song hong": "Đồng bằng sông Hồng",
    "bac trung bo": "Bắc Trung Bộ",
    "nam trung bo": "Nam Trung Bộ",
    # ── Viết tắt phổ biến ────────────────────────────────────────────────────
    "dn": "Đà Nẵng",
    "hn": "Hà Nội",
    "hcm": "TP.HCM",
    "sg": "TP.HCM",
    "hp": "Hải Phòng",
    "ct": "Cần Thơ",
    "dl": "Đà Lạt",
    "bmt": "Đắk Lắk",
    "qn": "Quảng Nam",
    "qni": "Quảng Ngãi",
    "bd": "Bình Định",
    "py": "Phú Yên",
    "kh": "Khánh Hòa",
    "nt": "Ninh Thuận",
    "bt": "Bình Thuận",
    "gl": "Gia Lai",
    "kt": "Kon Tum",
    "dln": "Đắk Nông",
    "la": "Lâm Đồng",
    "vt": "Bà Rịa - Vũng Tàu",
    "tg": "Tiền Giang",
    "ag": "An Giang",
    "kg": "Kiên Giang",
    "hg": "Hậu Giang",
    "st": "Sóc Trăng",
    "bl": "Bạc Liêu",
    "cm": "Cà Mau",
}


def normalize_user_text(message: str) -> str:
    text = (message or "").lower().replace("đ", "d")  # đ (U+0111) doesn't decompose via NFD
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_intent(intent: str | None) -> str:
    normalized = (intent or "general_question").strip()
    return INTENT_ALIASES.get(normalized, normalized)


def db_topic_for_intent(intent: str | None) -> str:
    return DB_TOPIC_BY_INTENT.get(intent or "", DB_TOPIC_BY_INTENT.get(normalize_intent(intent), "Khac"))


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _has_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None


def _is_greeting_only(text: str) -> bool:
    if not text:
        return False
    greeting_phrases = {
        "chao",
        "chao ban",
        "xin chao",
        "hello",
        "hi",
        "alo",
        "ban oi",
        "chao ad",
        "chao anh",
        "chao chi",
        "chao em",
        "hey",
    }
    if text in greeting_phrases:
        return True
    words = text.split()
    if len(words) <= 4:
        return text.startswith(("chao ", "xin chao", "hello", "hi ", "alo", "hey ", "ban oi"))
    return False


def classify_user_intent(message: str) -> str:
    """Rule-based classifier for the AI Chat router.

    The rules intentionally avoid treating the normalized word "ban" as "bán"
    by itself because it is also the common greeting word "bạn".
    """
    text = normalize_user_text(message)
    if not text:
        return "general_question"

    full_farm_keywords = (
        "phan tich tong quan",
        "tong quan hom nay",
        "tinh hinh nong trai",
        "tinh hinh trang trai",
        "phan tich tinh hinh nong trai",
        "phan tich tinh hinh trang trai",
        "cho toi loi khuyen hom nay",
        "loi khuyen hom nay",
        "hom nay nen lam gi",
        "bao cao tong hop",
        "tong hop hom nay",
    )
    price_keywords = (
        "gia ca",
        "gia nong san",
        "thi truong",
        "du bao gia",
        "xu huong gia",
        "bao nhieu tien",
        "co nen ban",
        "nen ban",
        "ban khong",
        "ban hang",
        "giu hang",
        "giu lai",
        "xuat hang",
        "thu mua",
        "dinh gia",
    )
    weather_keywords = (
        "thoi tiet",
        "du bao thoi tiet",
        "mua khong",
        "co mua",
        "troi mua",
        "mua lon",
        "nang",
        "nang nong",
        "tuoi",
        "nen tuoi",
        "co nen tuoi",
        "phun",
        "do am",
        "nhiet do",
        "bao so",
        "giong bao",
        "ap thap",
        "lu lut",
        "lu quet",
        "han han",
        "ret",
        "suong muoi",
        "ngap",
        "rui ro thoi tiet",
    )
    harvest_keywords = (
        "mua vu",
        "thu hoach",
        "lich thu hoach",
        "khi nao thu hoach",
        "ngay cat",
        "xuong giong",
        "gieo sa",
        "gieo trong",
        "lich gieo",
        "ngay du kien thu hoach",
        "giai doan hien tai",
        "sau thu hoach",
        "bao quan",
    )
    cultivation_keywords = (
        "ky thuat trong",
        "ky thuat canh tac",
        "cach trong",
        "huong dan trong",
        "trong cay",
        "canh tac",
        "phan bon",
        "bon phan",
        "mat do trong",
        "khoang cach trong",
        "chuan bi dat",
        "lam dat",
        "dat trong",
        "giong cay",
        "giong nao",
    )
    quality_keywords = (
        "chat luong",
        "loai may",
        "loai 1",
        "loai mot",
        "loai 2",
        "loai hai",
        "loai 3",
        "loai ba",
        "sau benh",
        "sau hai",
        "benh",
        "anh nay",
        "hinh anh",
        "hinh nay",
        "kiem dinh",
        "kiem tra chat luong",
        "nong san cua toi",
        "dau hieu benh",
        "la vang",
        "dom la",
    )
    alert_keywords = (
        "canh bao",
        "rui ro",
        "nguy hiem",
        "can chu y gi",
        "luu y gi",
        "co canh bao gi",
        "bat thuong",
    )
    general_keywords = (
        "ban lam duoc gi",
        "ai nay ho tro gi",
        "ho tro gi",
        "huong dan",
        "cach dung",
        "su dung he thong",
        "chuc nang",
        "tro ly nay",
        "gioi thieu",
    )

    if _contains_any(text, full_farm_keywords):
        return "full_farm_analysis"
    if _contains_any(text, price_keywords) or _has_word(text, "gia"):
        return "price_analysis"
    if _contains_any(text, weather_keywords) or _has_word(text, "gio"):
        return "weather_analysis"
    if _contains_any(text, cultivation_keywords):
        return "cultivation_advice"
    if _contains_any(text, harvest_keywords):
        return "harvest_analysis"
    if _contains_any(text, quality_keywords):
        return "quality_analysis"
    if _contains_any(text, alert_keywords):
        return "alert_analysis"
    if _is_greeting_only(text):
        return "greeting"
    if _contains_any(text, general_keywords):
        return "general_question"
    return "general_question"


def is_capability_question(message: str) -> bool:
    text = normalize_user_text(message)
    return _contains_any(
        text,
        (
            "ban lam duoc gi",
            "ai nay ho tro gi",
            "ho tro gi",
            "huong dan",
            "cach dung",
            "su dung he thong",
            "chuc nang",
            "tro ly nay",
            "gioi thieu",
        ),
    )


def extract_region_from_message(message: str) -> str | None:
    text = normalize_user_text(message)
    for keyword, region in REGION_KEYWORDS.items():
        if keyword in text:
            return region
    return None


def extract_crop_from_message(message: str) -> str | None:
    text = normalize_user_text(message)
    if not text:
        return None
    try:
        from app.services.pricing_service import pricing_service

        crops = pricing_service.crop_base_prices.keys()
    except Exception:
        crops = (
            "ca chua",
            "lua",
            "ngo",
            "sau rieng",
            "ca phe",
            "ho tieu",
            "tieu",
            "xoai",
            "thanh long",
            "chuoi",
        )
    for crop in sorted(crops, key=len, reverse=True):
        if normalize_user_text(crop) in text:
            return crop
    return None
