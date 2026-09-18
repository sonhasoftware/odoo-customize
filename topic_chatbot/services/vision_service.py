# -*- coding: utf-8 -*-
import base64
import json
import logging
import os
import requests
from . import ocr_service

_logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 60


def call_ollama_vision(ollama_url, model_name, image_bytes, num_threads=8, timeout=60, prompt=None):
    """Call Ollama /api/generate with an image payload and num_thread control."""
    target_url = (ollama_url or 'http://localhost:11434').rstrip('/')
    target_model = model_name or 'qwen2-vl:2b'

    default_prompt = (
        "Đây là một hình ảnh sơ đồ/quy trình hoặc biểu đồ. "
        "Hãy mô tả chi tiết sơ đồ, cấu trúc các khối, các bước quy trình theo thứ tự luân chuyển, "
        "và các điều kiện rẽ nhánh (nếu có) bằng tiếng Việt rõ ràng, mạch lạc."
    )
    prompt_text = prompt or default_prompt
    img_b64 = base64.b64encode(image_bytes).decode('utf-8')

    payload = {
        "model": target_model,
        "prompt": prompt_text,
        "images": [img_b64],
        "stream": False,
        "options": {
            "num_thread": int(num_threads or 8),
            "temperature": 0.1
        }
    }

    url = f"{target_url}/api/generate"
    res = requests.post(url, json=payload, timeout=timeout)
    if res.status_code == 200:
        data = res.json()
        return data.get('response', '').strip()
    else:
        raise RuntimeError(f"Ollama Vision API HTTP {res.status_code}: {res.text[:200]}")


def call_gemini_vision(env, image_bytes, prompt=None):
    """Call Google Gemini Vision API for diagram interpretation."""
    params = env['ir.config_parameter'].sudo()
    api_key = params.get_param('topic_chatbot.gemini_api_key')
    if not api_key:
        raise RuntimeError("Chưa cấu hình Gemini API Key cho Vision fallback.")

    default_prompt = (
        "Đây là một hình ảnh sơ đồ/quy trình hoặc biểu đồ. "
        "Hãy mô tả chi tiết sơ đồ, cấu trúc các khối, các bước quy trình theo thứ tự luân chuyển, "
        "và các điều kiện rẽ nhánh (nếu có) bằng tiếng Việt rõ ràng, mạch lạc."
    )
    prompt_text = prompt or default_prompt
    img_b64 = base64.b64encode(image_bytes).decode('utf-8')

    models_to_try = [
        'gemini-2.5-flash',
        'gemini-3.6-flash',
        'gemini-2.0-flash',
        'gemini-1.5-flash',
    ]

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt_text},
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}},
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 4096
            }
        }
        try:
            res = requests.post(url, json=payload, timeout=45)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    if parts and 'text' in parts[0]:
                        return parts[0]['text'].strip()
            elif res.status_code == 429:
                _logger.warning("Gemini Vision rate limited on %s", model_name)
                continue
        except Exception as e:
            _logger.warning("Gemini Vision model %s error: %s", model_name, str(e))
            continue

    raise RuntimeError("Không thể phân tích sơ đồ qua Gemini Cloud Vision.")


def call_vision_ocr(env, image_bytes, prompt=None):
    """Main routing function for diagram / flowchart VLM processing.

    Respects settings:
      - topic_chatbot.vision_provider: 'ollama' | 'gemini' | 'none'
      - topic_chatbot.ollama_vision_model: e.g. 'qwen2-vl:2b'
      - topic_chatbot.ocr_num_threads: e.g. 8
      - Timeout: 60s with automatic fallback to Gemini if API key configured.
    """
    params = env['ir.config_parameter'].sudo()
    provider = params.get_param('topic_chatbot.vision_provider') or 'ollama'

    if provider == 'none':
        return ""

    if provider == 'ollama':
        ollama_url = params.get_param('topic_chatbot.ollama_url') or 'http://localhost:11434'
        model_name = params.get_param('topic_chatbot.ollama_vision_model') or 'qwen2-vl:2b'
        
        # Determine dynamic num_threads from config or hardware
        raw_threads = params.get_param('topic_chatbot.ocr_num_threads')
        try:
            num_threads = int(raw_threads) if raw_threads else max(1, (os.cpu_count() or 4) - 2)
        except Exception:
            num_threads = max(1, (os.cpu_count() or 4) - 2)

        try:
            return call_ollama_vision(
                ollama_url, model_name, image_bytes,
                num_threads=num_threads, timeout=TIMEOUT_SECONDS, prompt=prompt
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, Exception) as err:
            _logger.warning("Ollama Vision call failed or timed out (%s): %s. Checking Gemini fallback...", model_name, str(err))
            gemini_key = params.get_param('topic_chatbot.gemini_api_key')
            if gemini_key:
                _logger.info("Falling back to Gemini Cloud Vision for diagram image.")
                try:
                    return call_gemini_vision(env, image_bytes, prompt)
                except Exception as gemini_err:
                    _logger.error("Gemini Vision fallback also failed: %s", str(gemini_err))
            return f"[Sơ đồ / Lưu đồ: Không thể trích xuất do Ollama Vision quá tải hoặc timeout 60s ({str(err)})]"

    elif provider == 'gemini':
        return call_gemini_vision(env, image_bytes, prompt)

    return ""


def call_dual_route_fusion(env, image_bytes, ocr_prompt=None, vision_prompt=None):
    """Execute both OCR engine and Vision model sequentially and merge results.
    
    Used for 'mixed' images (confidence score 0.40 - 0.60) to guarantee
    neither numerical table figures nor process diagrams are lost.
    """
    ocr_result = ""
    vision_result = ""

    # 1. Deterministic OCR pass
    try:
        ocr_result = ocr_service.call_ocr_engine(env, image_bytes, prompt=ocr_prompt)
    except Exception as e:
        _logger.warning("Dual-route OCR pass failed: %s", str(e))
        ocr_result = f"[Lỗi trích xuất bảng số liệu: {str(e)}]"

    # 2. VLM Vision pass
    try:
        vision_result = call_vision_ocr(env, image_bytes, prompt=vision_prompt)
    except Exception as e:
        _logger.warning("Dual-route Vision pass failed: %s", str(e))
        vision_result = f"[Lỗi diễn giải sơ đồ: {str(e)}]"

    merged_parts = []
    if ocr_result and ocr_result.strip():
        merged_parts.append(f"📊 **[Văn bản & Bảng số liệu trong ảnh]:**\n{ocr_result.strip()}")
    if vision_result and vision_result.strip():
        merged_parts.append(f"🔄 **[Diễn giải Sơ đồ & Tiến trình liên quan]:**\n{vision_result.strip()}")

    return "\n\n".join(merged_parts)
