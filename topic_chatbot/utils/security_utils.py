# -*- coding: utf-8 -*-
import json
import logging

_logger = logging.getLogger(__name__)

DEPRECATED_GEMINI_MODEL_MAP = {
    'gemini-1.5-flash': 'gemini-3.5-flash-lite',
    'gemini-1.5-pro': 'gemini-3.1-pro-preview',
    'gemini-2.0-flash': 'gemini-3.6-flash',
    'gemini-2.0-flash-001': 'gemini-3.6-flash',
    'gemini-2.0-flash-lite': 'gemini-3.5-flash-lite',
    'gemini-2.0-flash-lite-001': 'gemini-3.5-flash-lite',
}


def normalize_model_name(model):
    """Normalize and map deprecated Gemini model names to active equivalents."""
    clean = (model or 'gemini-3.6-flash').replace('models/', '').strip()
    return DEPRECATED_GEMINI_MODEL_MAP.get(clean, clean) or 'gemini-3.6-flash'


def redact_api_key(value, api_key):
    """Mask sensitive API key occurrences in text or exception logs."""
    if value and api_key:
        return str(value).replace(api_key, 'REDACTED')
    return value


def extract_gemini_error(response, api_key=None):
    """Return sanitized Gemini error details for logging and user messaging."""
    details = {
        'status_code': getattr(response, 'status_code', None),
        'status': '',
        'message': '',
        'raw': '',
    }
    try:
        data = response.json()
        error = data.get('error', {}) if isinstance(data, dict) else {}
        details['status'] = error.get('status') or ''
        details['message'] = error.get('message') or ''
    except Exception:
        details['raw'] = getattr(response, 'text', '') or ''

    for key in ('status', 'message', 'raw'):
        details[key] = redact_api_key(details[key], api_key)
    return details


def gemini_user_error_message(status_code=None, error_status='', error_message=''):
    """Map Gemini/API transport failures to an actionable user-facing message."""
    normalized_status = (error_status or '').upper()
    normalized_message = (error_message or '').lower()

    if status_code == 429 or normalized_status == 'RESOURCE_EXHAUSTED':
        return (
            "Gemini API đang bị giới hạn lượt gọi/quota (429). "
            "Vui lòng chờ một lát rồi thử lại, hoặc kiểm tra quota và billing của API key."
        )
    if status_code in (401, 403) or normalized_status in ('UNAUTHENTICATED', 'PERMISSION_DENIED'):
        return (
            "Gemini API key không hợp lệ, hết quyền truy cập, hoặc chưa bật quyền cho model đang dùng. "
            "Vui lòng kiểm tra lại API key trong Cấu hình."
        )
    if status_code == 404 or normalized_status == 'NOT_FOUND':
        return (
            "Model Gemini đang cấu hình không tồn tại hoặc không còn được hỗ trợ. "
            "Vui lòng chọn lại model trong Cấu hình chatbot."
        )
    if status_code == 400 or normalized_status == 'INVALID_ARGUMENT':
        if 'api key' in normalized_message:
            return "Gemini API key không hợp lệ. Vui lòng kiểm tra lại API key trong Cấu hình."
        return (
            "Gemini từ chối yêu cầu do dữ liệu gửi lên chưa hợp lệ. "
            "Vui lòng thử lại với câu hỏi ngắn hơn hoặc kiểm tra cấu hình chatbot."
        )
    if status_code and status_code >= 500:
        return "Gemini API đang gặp lỗi tạm thời. Vui lòng thử lại sau ít phút."
    return "Đã xảy ra lỗi khi kết nối tới Gemini API. Vui lòng thử lại sau."
