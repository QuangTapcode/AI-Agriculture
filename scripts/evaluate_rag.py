"""Chạy bộ 30 câu hỏi đánh giá qua trợ lý thật và ghi kết quả ra JSONL.

Script gọi đúng endpoint mà người dùng gọi (`POST /api/ai-chat/message`) chứ
không dựng lại pipeline bên trong. Dựng lại thì chỉ đo được đoạn code mà
script này biết, còn cổng grounding, bộ nhớ hội thoại và lớp bảo đảm trích dẫn
nằm ở endpoint sẽ không được đo — tức là đo một hệ thống không ai dùng.

    python scripts/evaluate_rag.py --base-url http://127.0.0.1:8000
    python scripts/evaluate_rag.py --review        # duyệt tay các lượt cần người xác nhận

Mỗi dòng JSONL là kết quả một câu hỏi: câu trả lời sinh ra, trích dẫn thực tế,
độ trễ và kết luận. Kết quả được ghi ngay sau mỗi lượt, nên một lần chạy đứt
giữa chừng vẫn giữ được phần đã đo.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter, sleep

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
QUESTIONS_PATH = ROOT / "docs" / "challenge" / "evaluation_questions.json"
MANIFEST_PATH = ROOT / "docs" / "challenge" / "dataset_manifest.json"
RESULTS_PATH = ROOT / "docs" / "challenge" / "evaluation_results.jsonl"


def _duong_dan_ngan(path: Path) -> str:
    """Đường dẫn gọn khi nằm trong repo, tuyệt đối khi người dùng trỏ ra ngoài."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _load_questions(path: Path) -> dict:
    """Load the evaluator JSON schema or the challenge JSONL schema."""
    if path.suffix.lower() == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        questions = []
        for row in rows:
            if row["answerable"]:
                category = "grounded"
                expected_behavior = "answer_with_citation"
            elif row["category"] == "out_of_scope":
                category = "out_of_scope"
                expected_behavior = "out_of_scope_refusal"
            else:
                category = "no_source"
                expected_behavior = "insufficient_data"
            questions.append({
                "id": row["id"],
                "category": category,
                "expected_behavior": expected_behavior,
                "expected_doc_ids": row["expected_source"],
                "question": row["question"],
                "ground_truth": row.get("ground_truth", ""),
                "original_category": row["category"],
            })
        return {"version": "evaluation-jsonl", "questions": questions}
    return json.loads(path.read_text(encoding="utf-8"))

TU_CHOI_THIEU_DU_LIEU = "chưa đủ dữ liệu"
DAU_HIEU_NGOAI_PHAM_VI = "ngoài lĩnh vực nông nghiệp"

# Cổng grounding luôn dùng đúng một câu chữ. Model thì diễn đạt mỗi lần một
# khác — đo thật thấy "Không có dữ liệu trong tài liệu truy xuất về...",
# "Dữ liệu hiện có không cung cấp thông tin...". Cùng một ý từ chối, nên đều
# phải nhận ra; chỗ khác nhau (ai từ chối) được xét riêng bên dưới.
_CACH_NOI_TU_CHOI = (
    "chưa đủ dữ liệu", "chưa có dữ liệu", "không có dữ liệu",
    "không cung cấp thông tin", "chưa có nguồn", "không có thông tin",
    "không có đoạn tài liệu", "chưa có tài liệu",
)


# Các intent mà nguồn chính là số liệu đo được trong DB, không phải tài liệu.
# Giữ khớp với app/services/grounding_policy.py.
INTENT_NEO_BANG_SO_LIEU = frozenset({
    "price_analysis", "weather_analysis", "harvest_analysis",
    "alert_analysis", "full_farm_analysis",
})

CHAN_NGUON = "nguồn tham khảo:"


def _la_cau_tu_choi(thap: str) -> bool:
    return any(cach_noi in thap for cach_noi in _CACH_NOI_TU_CHOI)


def _loi_cua_model(thap: str) -> str:
    """Phần model tự viết, bỏ chân nguồn mà hệ thống gắn thêm.

    bao_dam_trich_dan gắn danh sách nguồn vào mọi câu trả lời có sources, kể
    cả câu chỉ có từ chối. Không tách ra thì một lời từ chối thuần vẫn trông
    như có trích dẫn.
    """
    return thap.split(CHAN_NGUON)[0]


def _tu_choi_hoan_toan(thap: str) -> bool:
    """Từ chối mà không viện dẫn đoạn tài liệu nào.

    Từ chối TỪNG PHẦN là hành vi được yêu cầu — system prompt bảo model nói
    thẳng "chưa đủ dữ liệu cho phần này" ở chỗ tài liệu không nói tới, và câu
    trả lời kiểu đó vẫn trích dẫn [TLn] cho phần nó trả lời được. Từ chối
    thuần thì không trích dẫn gì, vì không có gì để trích.
    """
    loi_model = _loi_cua_model(thap)
    return _la_cau_tu_choi(loi_model) and "[tl" not in loi_model


# ── Chấm điểm ────────────────────────────────────────────────────────────────
#
# Tách khỏi phần gọi mạng để test được mà không cần LLM; xem
# backend/tests/test_evaluate_rag_scoring.py.


def _la_nam(chuoi: str) -> bool:
    """1900-2100 viết liền: gần như chắc chắn là năm, không phải số liệu."""
    return chuoi.isdigit() and len(chuoi) == 4 and 1900 <= int(chuoi) <= 2100


def _so_lieu_bia(tra_loi: str, doan_trich: str) -> list[str]:
    """Dùng lại chốt chặn số bịa của hệ thống làm luật chấm.

    Bỏ năm ra khỏi kết quả: chốt chặn coi mọi cụm từ 4 chữ số trở lên là số
    liệu thị trường — đúng cho "96.433 đ/kg", sai cho "2026-09-26" mà trợ lý
    mở đầu câu trả lời. Một luật chấm hay báo động giả sẽ bị bỏ qua, và lúc
    đó nó không còn bắt được con số bịa thật nữa.

    Import muộn: script phải import được trong test mà không kéo theo cả app.
    """
    sys.path.insert(0, str(BACKEND_ROOT))
    from app.integrations.ai_grounding import so_lieu_khong_co_trong_nguon

    return [so for so in so_lieu_khong_co_trong_nguon(tra_loi, doan_trich)
            if not _la_nam(so)]


def cham_diem(cau_hoi: dict, ban_ghi: dict) -> dict:
    """Kết luận cho một lượt hỏi.

    Ba nhóm câu hỏi được chấm theo ba chuẩn khác nhau. Nhóm thiếu nguồn và
    nhóm lạc đề chấm tự động trọn vẹn — chúng chỉ có một hành vi đúng. Nhóm có
    nguồn thì máy chỉ kiểm được hình thức (có trích dẫn không, có đúng tài
    liệu không, có chèn số lạ không); nội dung đúng hay sai vẫn cần người đọc,
    nên kết luận dừng ở "needs_review" thay vì tự phong là đạt.
    """
    tra_loi = (ban_ghi.get("generated_answer") or "").strip()
    thap = tra_loi.lower()
    grounding = ban_ghi.get("grounding") or {}
    trich_dan = ban_ghi.get("citations") or []
    notes: list[str] = []

    if ban_ghi.get("error"):
        return {"verdict": "fail", "checks": {}, "notes": ["request_failed"]}

    doan_trich = " ".join(str(item.get("excerpt") or "") for item in trich_dan)
    so_la = _so_lieu_bia(tra_loi, doan_trich)
    # Script chỉ thấy đoạn trích RAG, không thấy context backend. Với intent
    # được neo bằng số liệu đo (giá, thời tiết, mùa vụ), câu trả lời mang số
    # thật của backend — "áp suất 1009,3 hPa" — và script KHÔNG BIẾT nó từ
    # đâu. Kết luận "bịa" ở đó là nói quá những gì đo được, nên chuyển thành
    # ghi chú kèm danh sách số để người đọc tự đối chiếu.
    neo_bang_so_lieu = ban_ghi.get("intent") in INTENT_NEO_BANG_SO_LIEU
    khong_bia = not so_la or neo_bang_so_lieu
    if so_la and neo_bang_so_lieu:
        notes.append("so_lieu_chua_doi_chieu_duoc_voi_backend")

    if cau_hoi["category"] == "grounded":
        # Kho chia sẻ có 127 tài liệu chứ không chỉ 20 tài liệu corpus cố
        # định. Lấy một tài liệu khuyến nông khác đúng chủ đề thì câu trả lời
        # vẫn có thể đúng và có nguồn — máy không đọc hiểu để kết luận thay
        # được, nên chuyển cho người đọc thay vì đánh trượt.
        lay_duoc = set(ban_ghi.get("retrieved_doc_ids") or [])
        trung_mong_doi = bool(set(cau_hoi["expected_doc_ids"]) & lay_duoc)
        # Lấy nhầm một tài liệu KHÁC TRONG CORPUS là retrieval sai chứng minh
        # được: tài liệu đúng có trong kho mà không lên. Còn lấy tài liệu ngoài
        # corpus thì chưa kết luận được — nó vẫn có thể trả lời đúng câu hỏi.
        ngoai_corpus = bool(trich_dan) and not lay_duoc
        checks = {
            "co_cau_tra_loi": bool(tra_loi),
            "trang_thai_ready": grounding.get("status") == "ready",
            "co_trich_dan": bool(trich_dan) and ("[tl" in thap or "nguồn tham khảo" in thap),
            "khong_bia_so_lieu": khong_bia,
            "khong_lay_nham_tai_lieu_trong_corpus": trung_mong_doi or ngoai_corpus,
        }
        if not khong_bia:
            notes.append("so_lieu_khong_co_trong_doan_trich")
        # Máy không tách được "từ chối hẳn" khỏi "trả lời kèm ghi chú phần
        # thiếu". Đo trên 20 câu có nguồn: mọi câu trả lời đều dài 629–896 ký
        # tự nên độ dài vô dụng, và model bỏ trích dẫn inline ở 8/20 câu trả
        # lời tốt nên [TLn] cũng vô dụng. Đánh dấu để người đọc soi, không tự
        # kết luận. Ca hỏng thật — cổng từ chối một câu có nguồn — vẫn bị bắt
        # bởi trang_thai_ready và co_trich_dan.
        if _la_cau_tu_choi(_loi_cua_model(thap)):
            notes.append("co_cau_tu_choi_trong_cau_tra_loi")
        verdict = "needs_review" if all(checks.values()) else "fail"
        if verdict == "needs_review":
            notes.append("tai_lieu_ngoai_corpus_co_dinh" if ngoai_corpus
                         else "can_nguoi_doc_xac_nhan_noi_dung")
        return {"verdict": verdict, "checks": checks, "notes": notes,
                "so_lieu_khong_ro_nguon": so_la}

    if cau_hoi["category"] == "no_source":
        # Hai nguồn từ chối rất khác nhau về độ tin cậy: cổng grounding chặn
        # bằng luật, còn model tự từ chối là do nó ngoan lần này. Gộp chung
        # một kết luận là tính công cho sự may mắn.
        cong_chan = grounding.get("reason") == "thieu_nguon"
        checks = {
            "he_thong_tu_choi": _la_cau_tu_choi(thap),
            "khong_bia_so_lieu": khong_bia,
        }
        if not all(checks.values()):
            return {"verdict": "fail", "checks": checks, "notes": notes}
        if cong_chan:
            return {"verdict": "pass", "checks": {**checks, "cong_grounding_chan": True},
                    "notes": notes}
        notes.append("cong_khong_chan_model_tu_tu_choi")
        return {"verdict": "needs_review",
                "checks": {**checks, "cong_grounding_chan": False}, "notes": notes}

    checks = {
        "tu_choi_theo_pham_vi": DAU_HIEU_NGOAI_PHAM_VI in thap,
        "ly_do_ngoai_pham_vi": grounding.get("reason") == "ngoai_pham_vi",
        "khong_noi_nham_thieu_du_lieu": TU_CHOI_THIEU_DU_LIEU not in thap,
    }
    return {"verdict": "pass" if all(checks.values()) else "fail",
            "checks": checks, "notes": notes}


# ── Gọi trợ lý thật ──────────────────────────────────────────────────────────


def _ban_do_tai_lieu() -> dict[str, str]:
    """URL nguồn và tên file ingest -> id tài liệu trong manifest.

    Trích dẫn trả về từ API mang source_url và name; đối chiếu ngược lại để
    biết retrieval có lấy đúng tài liệu mong đợi hay không.
    """
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    ban_do: dict[str, str] = {}
    for item in payload["documents"]:
        ban_do[item["source_url"]] = item["id"]
        ban_do[item["ingest_filename"]] = item["id"]
    return ban_do


def _doc_id(nguon: dict, ban_do: dict[str, str]) -> str | None:
    for khoa in (nguon.get("source_url"), nguon.get("name"), nguon.get("source_name")):
        if khoa and khoa in ban_do:
            return ban_do[khoa]
    return None


def hoi_tro_ly(client, base_url: str, cau_hoi: dict, timeout: float, token: str | None) -> dict:
    """Một lượt hỏi, kèm độ trễ đo từ phía người dùng.

    session_id riêng cho từng câu: dùng chung một phiên thì lượt sau đọc được
    lượt trước và bài đánh giá đo nhầm trí nhớ hội thoại thay vì retrieval.
    """
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = {"message": cau_hoi["question"], "session_id": f"eval-{cau_hoi['id']}-{uuid.uuid4().hex[:8]}"}

    bat_dau = perf_counter()
    try:
        response = client.post(f"{base_url}/api/ai-chat/message", json=payload,
                               headers=headers, timeout=timeout)
        latency_ms = round((perf_counter() - bat_dau) * 1000, 1)
        body = response.json()
    except Exception as exc:  # mạng đứt, timeout, JSON hỏng
        return {"latency_ms": round((perf_counter() - bat_dau) * 1000, 1),
                "error": {"http_status": None, "code": type(exc).__name__, "message": str(exc)[:300]},
                "data": {}}

    if response.status_code != 200 or not body.get("success"):
        loi = body.get("error") or {}
        return {"latency_ms": latency_ms,
                "error": {"http_status": response.status_code,
                          "code": loi.get("code") or "HTTP_ERROR",
                          "message": (loi.get("message") or "")[:300]},
                "data": {}}
    return {"latency_ms": latency_ms, "error": None, "data": body.get("data") or {}}


def cho_backend_san_sang(base_url: str, so_giay: float) -> bool:
    """Đợi backend trả lời /health trước khi bắt đầu đo."""
    import httpx

    han = perf_counter() + max(0.0, so_giay)
    lan_dau = True
    while True:
        try:
            with httpx.Client(timeout=5.0) as client:
                if client.get(f"{base_url}/health").status_code == 200:
                    return True
        except Exception:
            pass
        if perf_counter() >= han:
            return False
        if lan_dau:
            print(f"Đang đợi backend tại {base_url} …")
            lan_dau = False
        sleep(2.0)


def chay(args) -> int:
    import httpx

    bo_de = _load_questions(args.questions)
    cac_cau = bo_de["questions"]
    if args.only:
        cac_cau = [item for item in cac_cau if item["category"] == args.only]
    if args.limit:
        cac_cau = cac_cau[: args.limit]
    if not cac_cau:
        print("Không có câu hỏi nào khớp bộ lọc.")
        return 1

    if not cho_backend_san_sang(args.base_url, args.wait):
        # Dừng TRƯỚC khi mở file kết quả. Mở bằng "w" rồi mới phát hiện backend
        # chưa lên thì file kết quả tốt của lần chạy trước đã bị xoá sạch, đổi
        # lấy 30 dòng lỗi — đúng chuyện vừa xảy ra khi chạy ngay sau
        # `docker compose up -d`.
        print(f"Backend tại {args.base_url} chưa sẵn sàng sau {args.wait:g}s. "
              f"Không chạy, và giữ nguyên {_duong_dan_ngan(args.out)}.")
        return 1

    ban_do = _ban_do_tai_lieu()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ghi = args.out.open("w", encoding="utf-8")

    ket_qua_all: list[dict] = []
    with httpx.Client() as client:
        for thu_tu, cau_hoi in enumerate(cac_cau, start=1):
            phan_hoi = hoi_tro_ly(client, args.base_url, cau_hoi, args.timeout, args.token)
            data = phan_hoi["data"]
            rag = data.get("rag") or {}
            nguon = rag.get("sources") or []
            trich_dan = [{
                "citation": item.get("citation"),
                "doc_id": _doc_id(item, ban_do),
                "name": item.get("name"),
                "source_name": item.get("source_name"),
                "source_url": item.get("source_url"),
                "page": item.get("page"),
                "score": item.get("score"),
                "excerpt": (item.get("excerpt") or "")[:600],
            } for item in nguon]

            ban_ghi = {
                "run_id": run_id,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "dataset_version": bo_de["version"],
                "id": cau_hoi["id"],
                "category": cau_hoi["category"],
                "question": cau_hoi["question"],
                "expected_behavior": cau_hoi["expected_behavior"],
                "expected_doc_ids": cau_hoi["expected_doc_ids"],
                "intent": data.get("intent"),
                "provider": data.get("provider"),
                "model": data.get("model"),
                "timings": data.get("timings") or {},
                "grounding": data.get("grounding") or {},
                "rag_status": rag.get("status"),
                "generated_answer": data.get("reply") or "",
                "citations": trich_dan,
                "retrieved_doc_ids": [item["doc_id"] for item in trich_dan if item["doc_id"]],
                "latency_ms": phan_hoi["latency_ms"],
                "error": phan_hoi["error"],
            }
            ban_ghi["result"] = cham_diem(cau_hoi, ban_ghi)
            ban_ghi["human_review"] = None

            ghi.write(json.dumps(ban_ghi, ensure_ascii=False) + "\n")
            ghi.flush()
            ket_qua_all.append(ban_ghi)
            print(f"[{thu_tu:02d}/{len(cac_cau)}] {cau_hoi['id']} {cau_hoi['category']:<13} "
                  f"{ban_ghi['result']['verdict']:<12} {ban_ghi['latency_ms']:>8.0f} ms"
                  + (f"  ({ban_ghi['error']['code']})" if ban_ghi["error"] else ""))

    ghi.close()
    tom_tat(ket_qua_all)
    print(f"\nĐã ghi {len(ket_qua_all)} dòng vào {_duong_dan_ngan(args.out)}")
    return 0


def tom_tat(rows: list[dict]) -> None:
    print("\n── Tổng hợp ─────────────────────────────────────────")
    theo_nhom: dict[str, dict[str, int]] = {}
    for row in rows:
        verdict = (row.get("human_review") or {}).get("verdict") or row["result"]["verdict"]
        theo_nhom.setdefault(row["category"], {}).setdefault(verdict, 0)
        theo_nhom[row["category"]][verdict] += 1
    for nhom, dem in sorted(theo_nhom.items()):
        chi_tiet = ", ".join(f"{k}={v}" for k, v in sorted(dem.items()))
        print(f"  {nhom:<13} {chi_tiet}")

    co_nguon = [r for r in rows if r["category"] == "grounded"]
    if co_nguon:
        trung = sum(1 for r in co_nguon if set(r["expected_doc_ids"]) & set(r["retrieved_doc_ids"]))
        print(f"  retrieval hit  {trung}/{len(co_nguon)}")

    do_tre = sorted(r["latency_ms"] for r in rows if r["latency_ms"])
    if do_tre:
        p95 = do_tre[min(len(do_tre) - 1, int(len(do_tre) * 0.95))]
        print(f"  latency        p50={statistics.median(do_tre):.0f} ms  p95={p95:.0f} ms  "
              f"max={do_tre[-1]:.0f} ms")

    loi = [r for r in rows if r["error"]]
    if loi:
        print(f"  lượt lỗi       {len(loi)}/{len(rows)} — {loi[0]['error']['code']}")


# ── Duyệt tay phần máy không kết luận được ───────────────────────────────────


def _doc_ket_qua(path: Path) -> list[dict]:
    return [json.loads(dong) for dong in path.read_text(encoding="utf-8").splitlines() if dong.strip()]


def _ghi_ket_qua(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                    encoding="utf-8")


def cham_lai(args) -> int:
    """Chấm lại file kết quả đã có, không gọi lại model.

    Luật chấm còn sửa nhiều lần; bắt chạy lại 30 lượt gọi LLM mỗi lần sửa thì
    hoặc là mất nửa tiếng, hoặc là người ta thôi không sửa luật nữa. Câu trả
    lời đã lưu nguyên văn rồi — đủ để kết luận lại.
    """
    if not args.out.exists():
        print(f"Chưa có {_duong_dan_ngan(args.out)}. Chạy đánh giá trước.")
        return 1
    bo_de = {item["id"]: item for item in _load_questions(args.questions)["questions"]}
    rows = _doc_ket_qua(args.out)
    doi = 0
    for row in rows:
        cu = row["result"]["verdict"]
        row["result"] = cham_diem(bo_de[row["id"]], row)
        if row["result"]["verdict"] != cu:
            doi += 1
            print(f"  {row['id']}: {cu} -> {row['result']['verdict']}")
    _ghi_ket_qua(args.out, rows)
    print(f"Đã chấm lại {len(rows)} dòng, {doi} dòng đổi kết luận.")
    tom_tat(rows)
    return 0


def duyet(args) -> int:
    if not args.out.exists():
        print(f"Chưa có {args.out}. Chạy đánh giá trước.")
        return 1
    rows = _doc_ket_qua(args.out)
    can_duyet = [r for r in rows if r["result"]["verdict"] == "needs_review" and not r["human_review"]]
    if not can_duyet:
        print("Không còn lượt nào chờ duyệt.")
        tom_tat(rows)
        return 0

    print(f"{len(can_duyet)} lượt chờ duyệt. [d]ạt / [t]rượt / [b]ỏ qua / [q]uit\n")
    for row in can_duyet:
        print("─" * 70)
        print(f"{row['id']} — {row['question']}")
        print(f"Tài liệu lấy được: {row['retrieved_doc_ids']} (mong đợi {row['expected_doc_ids']})")
        print(f"\n{row['generated_answer']}\n")
        tra_loi = input("Kết luận? ").strip().lower()
        if tra_loi.startswith("q"):
            break
        if tra_loi.startswith("b"):
            continue
        ghi_chu = input("Ghi chú (bỏ trống nếu không có): ").strip()
        row["human_review"] = {
            "verdict": "pass" if tra_loi.startswith("d") else "fail",
            "note": ghi_chu or None,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }

    args.out.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8",
    )
    print(f"\nĐã cập nhật {_duong_dan_ngan(args.out)}")
    tom_tat(rows)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000",
                        help="Backend đang chạy (mặc định %(default)s).")
    parser.add_argument("--out", type=Path, default=RESULTS_PATH)
    parser.add_argument("--questions", type=Path, default=QUESTIONS_PATH,
                        help="Bộ đề JSON hoặc JSONL (mặc định evaluation_questions.json).")
    parser.add_argument("--only", choices=("grounded", "no_source", "out_of_scope"),
                        help="Chỉ chạy một nhóm câu hỏi.")
    parser.add_argument("--limit", type=int, help="Chỉ chạy N câu đầu — dùng để thử nhanh.")
    parser.add_argument("--timeout", type=float, default=180.0, help="Giây cho mỗi lượt hỏi.")
    parser.add_argument("--wait", type=float, default=60.0,
                        help="Giây chờ backend sẵn sàng trước khi đo (mặc định %(default)s).")
    parser.add_argument("--token", help="Bearer token nếu backend yêu cầu đăng nhập.")
    parser.add_argument("--review", action="store_true",
                        help="Duyệt tay các lượt máy không kết luận được, thay vì chạy mới.")
    parser.add_argument("--rescore", action="store_true",
                        help="Chấm lại file kết quả đã có bằng luật chấm hiện tại.")
    args = parser.parse_args()
    if args.rescore:
        return cham_lai(args)
    return duyet(args) if args.review else chay(args)


if __name__ == "__main__":
    raise SystemExit(main())
