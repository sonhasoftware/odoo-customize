# -*- coding: utf-8 -*-
"""
Crypto utilities for topic_chatbot module.

Cung cấp mã hóa đối xứng Fernet (AES-128-CBC + HMAC-SHA256) cho các tham số
cấu hình nhạy cảm (mật khẩu SQL Server, API key...) trước khi lưu vào bảng
ir_config_parameter của PostgreSQL.

Thiết kế key:
    - Key được KDF (PBKDF2-HMAC-SHA256, 200_000 vòng) từ `database.secret`
      của Odoo — chuỗi ngẫu nhiên 50 ký tự được tạo tự động theo từng DB.
    - Không cần lưu key riêng; key "gắn liền" với database instance đó.

Giới hạn bảo mật (cần ghi nhận):
    - Nếu kẻ tấn công có TOÀN BỘ DB dump (bao gồm cả database.secret) và
      biết thuật toán này, về lý thuyết họ vẫn có thể decrypt.
    - Giải pháp này bảo vệ chống: SQL injection đọc ir_config_parameter,
      partial dump, log leak, và truy cập thủ công qua Odoo UI.
    - Bảo vệ tuyệt đối đòi hỏi external key store (HSM/Vault/env variable).

Prefix convention:
    - Giá trị chưa mã hóa (legacy):  "MyP@ssw0rd"
    - Giá trị đã mã hóa:             "tc_enc:gAAAAABl..."
"""

import base64
import logging

_logger = logging.getLogger(__name__)

# Prefix nhận biết giá trị đã mã hóa — không được thay đổi sau khi deploy
_ENCRYPTION_PREFIX = 'tc_enc:'

# Salt cố định cho PBKDF2 — gắn với module và phiên bản mã hóa
_KDF_SALT = b'topic_chatbot_mssql_v1'

# Số vòng KDF — đủ chậm để brute-force khó, đủ nhanh cho runtime (~0.3s/lần)
_KDF_ITERATIONS = 200_000


def _get_fernet(env):
    """
    Tạo Fernet instance với key được derive từ database.secret của Odoo.

    Args:
        env: Odoo Environment object (request.env hoặc self.env)

    Returns:
        cryptography.fernet.Fernet instance

    Raises:
        ImportError: nếu thư viện 'cryptography' chưa được cài đặt
        ValueError: nếu database.secret không tồn tại
    """
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    db_secret = env['ir.config_parameter'].sudo().get_param('database.secret', '')
    if not db_secret:
        raise ValueError(
            "Odoo 'database.secret' không tồn tại. "
            "Không thể khởi tạo encryption key cho topic_chatbot."
        )

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KDF_SALT,
        iterations=_KDF_ITERATIONS,
    )
    key = base64.urlsafe_b64encode(kdf.derive(db_secret.encode('utf-8')))
    return Fernet(key)


def encrypt_value(env, plaintext: str) -> str:
    """
    Mã hóa một chuỗi văn bản thuần. Trả về chuỗi có dạng 'tc_enc:<token>'.

    - Nếu đầu vào đã có prefix 'tc_enc:', trả về nguyên bản (không mã hóa lại).
    - Nếu đầu vào rỗng/None, trả về nguyên bản.
    - Nếu thư viện 'cryptography' chưa cài, ghi log cảnh báo và trả về plaintext
      (fallback an toàn, không crash ứng dụng).

    Args:
        env: Odoo Environment
        plaintext: Chuỗi cần mã hóa (ví dụ: mật khẩu SQL Server)

    Returns:
        Chuỗi đã mã hóa với prefix 'tc_enc:', hoặc plaintext gốc nếu không mã hóa được
    """
    if not plaintext:
        return plaintext
    if plaintext.startswith(_ENCRYPTION_PREFIX):
        return plaintext  # Đã mã hóa, không xử lý lại

    try:
        f = _get_fernet(env)
        token = f.encrypt(plaintext.encode('utf-8'))
        return _ENCRYPTION_PREFIX + token.decode('utf-8')
    except ImportError:
        _logger.warning(
            "topic_chatbot [crypto_utils]: Thư viện 'cryptography' chưa được cài đặt. "
            "Mật khẩu SQL Server sẽ được lưu dạng PLAINTEXT. "
            "Khuyến nghị: pip install cryptography"
        )
        return plaintext
    except Exception as exc:
        _logger.error(
            "topic_chatbot [crypto_utils]: Lỗi không mong đợi khi mã hóa: %s. "
            "Fallback về plaintext.", str(exc)
        )
        return plaintext


def decrypt_value(env, value: str) -> str:
    """
    Giải mã một chuỗi 'tc_enc:<token>'. Trả về plaintext gốc.

    - Nếu giá trị KHÔNG có prefix 'tc_enc:', trả về nguyên bản (backward compatible
      với mật khẩu cũ đang lưu dạng plaintext).
    - Nếu token bị corrupt hoặc key sai, ghi log lỗi và trả về chuỗi rỗng.
    - Nếu thư viện 'cryptography' chưa cài, ghi log và trả về chuỗi rỗng.

    Args:
        env: Odoo Environment
        value: Chuỗi từ ir.config_parameter (có thể encrypted hoặc plaintext)

    Returns:
        Plaintext password, hoặc chuỗi rỗng nếu giải mã thất bại
    """
    if not value:
        return value or ''
    if not value.startswith(_ENCRYPTION_PREFIX):
        # Giá trị legacy (plaintext cũ) — dùng trực tiếp, backward compatible
        return value

    encrypted_token = value[len(_ENCRYPTION_PREFIX):]
    try:
        f = _get_fernet(env)
        decrypted = f.decrypt(encrypted_token.encode('utf-8'))
        return decrypted.decode('utf-8')
    except ImportError:
        _logger.warning(
            "topic_chatbot [crypto_utils]: Thư viện 'cryptography' chưa cài. "
            "Không thể giải mã mật khẩu SQL Server. Trả về chuỗi rỗng."
        )
        return ''
    except Exception as exc:
        _logger.error(
            "topic_chatbot [crypto_utils]: Lỗi giải mã mật khẩu — token có thể bị "
            "corrupt hoặc database.secret đã thay đổi: %s. Trả về chuỗi rỗng.", str(exc)
        )
        return ''


def is_encrypted(value: str) -> bool:
    """
    Kiểm tra xem một giá trị có đang ở dạng đã mã hóa không.

    Args:
        value: Chuỗi cần kiểm tra

    Returns:
        True nếu giá trị bắt đầu bằng prefix 'tc_enc:'
    """
    return bool(value and value.startswith(_ENCRYPTION_PREFIX))
