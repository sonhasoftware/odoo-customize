# -*- coding: utf-8 -*-
import base64
import json
import logging
import requests

_logger = logging.getLogger(__name__)

PADDLE_OCR_INSTANCE = None


def get_paddle_ocr_engine():
    """Lazily initialize PaddleOCR engine singleton on CPU."""
    global PADDLE_OCR_INSTANCE
    if PADDLE_OCR_INSTANCE is None:
        try:
            from paddleocr import PaddleOCR
            try:
                # Modern PaddleOCR versions (use_textline_orientation)
                PADDLE_OCR_INSTANCE = PaddleOCR(use_textline_orientation=True, lang='vi')
            except TypeError:
                # Older PaddleOCR fallback
                PADDLE_OCR_INSTANCE = PaddleOCR(use_angle_cls=True, lang='vi', use_gpu=False)
            _logger.info("PaddleOCR engine initialized successfully on CPU.")
        except ImportError:
            _logger.debug("PaddleOCR not installed in current Python environment.")
            PADDLE_OCR_INSTANCE = False
        except Exception as e:
            _logger.warning("Failed to initialize PaddleOCR: %s", str(e))
            PADDLE_OCR_INSTANCE = False
    return PADDLE_OCR_INSTANCE


def call_paddleocr(image_bytes):
    """Run PaddleOCR on image bytes and format output with line breaks."""
    engine = get_paddle_ocr_engine()
    if not engine:
        raise RuntimeError("PaddleOCR chưa được cài đặt trên máy chủ (pip install paddlepaddle paddleocr).")

    import io
    import numpy as np
    from PIL import Image

    stream = io.BytesIO(image_bytes)
    pil_img = Image.open(stream).convert('RGB')
    img_np = np.array(pil_img)

    result = engine.ocr(img_np, cls=True)
    pil_img.close()

    if not result or not result[0]:
        return ""

    lines = []
    for line in result[0]:
        if line and len(line) > 1 and line[1]:
            text_val = line[1][0]
            confidence = line[1][1]
            if text_val and confidence > 0.4:
                lines.append(text_val.strip())

    return "\n".join(lines)


def call_gemini_ocr(env, image_bytes, prompt=None):
    """Call Google Gemini Vision API as a high-fidelity fallback for text/tables."""
    params = env['ir.config_parameter'].sudo()
    api_key = params.get_param('topic_chatbot.gemini_api_key')
    if not api_key:
        raise RuntimeError("Chưa cấu hình Gemini API Key cho OCR fallback.")

    default_prompt = (
        "Hãy trích xuất toàn bộ văn bản, số liệu và bảng biểu trong hình ảnh này. "
        "Giữ nguyên định dạng bảng biểu dưới dạng Markdown (sử dụng dấu gạch đứng |). "
        "Không thêm bớt thông tin, không đoán số liệu mờ, chỉ trích xuất những gì có trong ảnh."
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
                "temperature": 0.0,
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
                _logger.warning("Gemini OCR rate limited on %s", model_name)
                continue
        except Exception as e:
            _logger.warning("Gemini OCR model %s error: %s", model_name, str(e))
            continue

    raise RuntimeError("Không thể trích xuất văn bản qua Gemini Cloud OCR.")


def call_ocr_engine(env, image_bytes, prompt=None):
    """Main routing function for deterministic text/table OCR.

    Respects settings:
      - topic_chatbot.ocr_provider: 'paddleocr' | 'gemini' | 'none'
    """
    params = env['ir.config_parameter'].sudo()
    provider = params.get_param('topic_chatbot.ocr_provider') or 'paddleocr'

    if provider == 'none':
        return ""

    if provider == 'paddleocr':
        try:
            res = call_paddleocr(image_bytes)
            if res and res.strip():
                return res
        except Exception as err:
            _logger.warning("PaddleOCR engine failed or not installed: %s. Checking Gemini fallback...", str(err))

        # Graceful fallback to Gemini if API key available
        gemini_key = params.get_param('topic_chatbot.gemini_api_key')
        if gemini_key:
            _logger.info("Falling back to Gemini Cloud OCR for text_table image.")
            return call_gemini_ocr(env, image_bytes, prompt)
        else:
            return "[Văn bản trong ảnh: PaddleOCR chưa được cài đặt và chưa cấu hình Gemini API Key]"

    elif provider == 'gemini':
        return call_gemini_ocr(env, image_bytes, prompt)

    return ""
