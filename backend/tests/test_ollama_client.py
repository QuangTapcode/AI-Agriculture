"""
TDD: trợ lý AI chạy local qua Ollama, không cần API key trả phí.

Client phải khớp đúng giao diện ClaudeClient đang dùng (get_farming_advice,
complete) để thay được mà không sửa tầng gọi.

Test bơm sẵn HTTP transport nên không cần Ollama chạy — chạy được trên CI
và trên máy chưa cài model.
"""
import json

import httpx
import pytest

from app.core.config import Settings
from app.integrations.ollama_client import OllamaClient

TRA_LOI = "Cà chua trồng tốt nhất vào tháng 9-10, đất tơi xốp thoát nước."


def test_local_model_defaults_fit_a_four_gigabyte_gpu_and_bound_response_time():
    config = Settings(_env_file=None)

    assert config.AI_CONTEXT_TOKENS == 3072
    assert config.AI_MAX_OUTPUT_TOKENS == 256
    assert config.RAG_MAX_CHUNKS_PER_DOCUMENT == 1


def _ollama_gia_lap(noi_dung=TRA_LOI, status=200):
    """Transport trả về đúng dạng payload của Ollama /api/chat."""
    def handler(request: httpx.Request) -> httpx.Response:
        if status != 200:
            return httpx.Response(status, json={"error": "model not found"})
        return httpx.Response(200, json={
            "model": "qwen2.5:7b-instruct-q4_K_M",
            "message": {"role": "assistant", "content": noi_dung},
            "prompt_eval_count": 120,
            "eval_count": 45,
            "done": True,
        })
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_tra_loi_cau_hoi_nong_nghiep():
    client = OllamaClient(transport=_ollama_gia_lap())

    answer = await client.get_farming_advice("Trồng cà chua tháng nào?")

    assert answer == TRA_LOI


@pytest.mark.asyncio
async def test_ollama_chet_thi_bao_loi_khong_bia():
    """Model chưa tải / Ollama chưa chạy => raise, không trả chuỗi giả.

    Đây đúng là lỗi vừa sửa ở gemini_client: nó trả "[Chế độ Test] câu trả
    lời giả lập..." vào thẳng trường answer, không cờ nào phân biệt.
    """
    client = OllamaClient(transport=_ollama_gia_lap(status=404))

    with pytest.raises(RuntimeError) as e:
        await client.get_farming_advice("Trồng cà chua tháng nào?")

    loi = str(e.value).lower()
    assert "giả lập" not in loi and "test" not in loi


@pytest.mark.asyncio
async def test_dua_du_lieu_he_thong_vao_prompt():
    """Model 7B không biết giá hôm nay — phải nhồi số liệu thật vào prompt."""
    nhan_duoc = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nhan_duoc["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "ok"}})

    client = OllamaClient(transport=httpx.MockTransport(handler))
    await client.get_farming_advice(
        "Giá cà phê hôm nay?", context_data="Cà phê Đắk Lắk: 96.433 đ/kg"
    )

    msgs = nhan_duoc["body"]["messages"]
    prompt = next(m["content"] for m in msgs if m["role"] == "user")
    assert "96.433" in prompt, "Số liệu thật không được đưa vào prompt"
    assert "Giá cà phê hôm nay?" in prompt


def test_complete_khop_giao_dien_claude():
    """complete() phải trả đúng shape ClaudeClient để thay được, không sửa caller."""
    client = OllamaClient(transport=_ollama_gia_lap())

    kq = client.complete([{"role": "user", "content": "Xin chào"}],
                         system_prompt="Bạn là chuyên gia nông nghiệp.")

    for key in ("answer", "provider", "model", "token_usage", "is_mock", "error"):
        assert key in kq, f"Thiếu khoá {key} — caller sẽ vỡ khi đổi provider"
    assert kq["answer"] == TRA_LOI
    assert kq["provider"] == "ollama"
    assert kq["is_mock"] is False
    assert kq["error"] is None


def test_complete_bao_cao_token_da_dung():
    """Có số token để theo dõi chi phí tính toán, dù chạy local là miễn phí."""
    client = OllamaClient(transport=_ollama_gia_lap())

    kq = client.complete([{"role": "user", "content": "Xin chào"}])

    assert kq["token_usage"]["input_tokens"] == 120
    assert kq["token_usage"]["output_tokens"] == 45


def test_complete_that_bai_khong_bao_la_mock():
    """Lỗi kết nối là LỖI, không phải dữ liệu giả — is_mock phải là False."""
    client = OllamaClient(transport=_ollama_gia_lap(status=500))

    kq = client.complete([{"role": "user", "content": "Xin chào"}])

    assert kq["error"], "Không đánh dấu lỗi"
    assert kq["is_mock"] is False


def test_qwen_hides_reasoning_and_requests_direct_answer():
    captured = {}
    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "Internal draft</think>\nCâu trả lời [TL1]."}})
    client = OllamaClient(model="qwen3:4b", transport=httpx.MockTransport(handler))
    original = [{"role": "user", "content": "Câu hỏi"}]
    result = client.complete(original)
    assert result["answer"] == "Câu trả lời [TL1]."
    assert captured["think"] is False
    assert captured["keep_alive"] == "15m"
    assert captured["messages"][-1]["content"].endswith("/no_think")
    assert original[0]["content"] == "Câu hỏi"
