# -*- coding: utf-8 -*-
import gc
import hashlib
import io
import logging
from PIL import Image, ImageOps

_logger = logging.getLogger(__name__)

UNSUPPORTED_VECTOR_FORMATS = {'wmf', 'emf', 'x-wmf', 'x-emf'}

def is_supported_image_format(content_type=None, filename=None):
    if content_type:
        clean_ct = content_type.lower().split('/')[-1].strip()
        if clean_ct in UNSUPPORTED_VECTOR_FORMATS:
            return False
    if filename:
        ext = filename.lower().split('.')[-1].strip()
        if ext in UNSUPPORTED_VECTOR_FORMATS:
            return False
    return True

def compute_image_md5(image_bytes):
    if not image_bytes:
        return None
    return hashlib.md5(image_bytes).hexdigest()

def filter_and_preprocess_image(image_bytes, min_dimension=150, min_size_bytes=8192, max_dimension=1600):
    """Filter and preprocess an image.
    
    Returns:
        tuple: (should_process: bool, reason: str, processed_bytes: bytes|None, img_hash: str)
    """
    if not image_bytes:
        return False, 'Dữ liệu ảnh rỗng (empty bytes)', None, ''

    raw_hash = compute_image_md5(image_bytes)

    if len(image_bytes) < min_size_bytes:
        return False, f'Kích thước file quá nhỏ ({len(image_bytes)} bytes < {min_size_bytes} bytes)', None, raw_hash

    pil_img = None
    try:
        stream = io.BytesIO(image_bytes)
        pil_img = Image.open(stream)

        fmt = (pil_img.format or '').lower()
        if fmt in UNSUPPORTED_VECTOR_FORMATS:
            return False, f'Bỏ qua định dạng vector không hỗ trợ ({fmt.upper()})', None, raw_hash

        try:
            pil_img = ImageOps.exif_transpose(pil_img)
        except Exception as exif_err:
            _logger.debug('EXIF transpose skipped: %s', str(exif_err))

        orig_w, orig_h = pil_img.size

        if orig_w < min_dimension or orig_h < min_dimension:
            return False, f'Độ phân giải quá nhỏ ({orig_w}x{orig_h} < {min_dimension}x{min_dimension})', None, raw_hash

        processed_img = pil_img
        if orig_w > max_dimension or orig_h > max_dimension:
            processed_img = pil_img.copy()
            processed_img.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            _logger.debug('Downscaled image from %dx%d to %dx%d', orig_w, orig_h, processed_img.width, processed_img.height)

        if processed_img.mode in ('RGBA', 'LA', 'P'):
            rgb_img = Image.new('RGB', processed_img.size, (255, 255, 255))
            if processed_img.mode == 'P':
                processed_img = processed_img.convert('RGBA')
            rgb_img.paste(processed_img, mask=processed_img.split()[-1] if 'A' in processed_img.mode else None)
            processed_img = rgb_img
        elif processed_img.mode != 'RGB':
            processed_img = processed_img.convert('RGB')

        out_stream = io.BytesIO()
        processed_img.save(out_stream, format='JPEG', quality=90, optimize=True)
        final_bytes = out_stream.getvalue()

        return True, 'OK', final_bytes, raw_hash

    except Exception as err:
        _logger.warning('Failed to inspect/preprocess image (hash %s): %s', raw_hash, str(err))
        return False, f'Lỗi đọc ảnh: {str(err)}', None, raw_hash

    finally:
        if pil_img:
            try:
                pil_img.close()
            except Exception:
                pass
        gc.collect()
