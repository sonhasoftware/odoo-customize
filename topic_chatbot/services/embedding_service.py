# -*- coding: utf-8 -*-
import json
import logging
import requests
import time

_logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = 'http://localhost:11434'
DEFAULT_OLLAMA_MODEL = 'bge-m3'
DEFAULT_GEMINI_EMBED_MODEL = 'gemini-embedding-2'


def get_embedding_config(env):
    """Retrieve embedding configuration parameters from ir.config_parameter."""
    params = env['ir.config_parameter'].sudo()
    provider = params.get_param('topic_chatbot.embedding_provider', default='gemini') or 'gemini'
    gemini_key = params.get_param('topic_chatbot.gemini_api_key') or ''
    gemini_model = params.get_param('topic_chatbot.embedding_model', default=DEFAULT_GEMINI_EMBED_MODEL) or DEFAULT_GEMINI_EMBED_MODEL
    ollama_url = (params.get_param('topic_chatbot.ollama_url') or DEFAULT_OLLAMA_URL).rstrip('/')
    ollama_model = params.get_param('topic_chatbot.ollama_model') or DEFAULT_OLLAMA_MODEL
    return {
        'provider': provider,
        'gemini_key': gemini_key,
        'gemini_model': gemini_model,
        'ollama_url': ollama_url,
        'ollama_model': ollama_model,
    }


def test_ollama_connection(url=None, model_name=None):
    """Test connection to Ollama local server and verify model availability."""
    target_url = (url or DEFAULT_OLLAMA_URL).rstrip('/')
    target_model = model_name or DEFAULT_OLLAMA_MODEL
    try:
        res = requests.get(f"{target_url}/api/tags", timeout=5)
        if res.status_code != 200:
            return {
                'success': False,
                'message': f"Không thể kết nối đến Ollama Server tại {target_url} (HTTP {res.status_code})."
            }
        data = res.json()
        models = [m.get('name', '') for m in data.get('models', [])]
        model_found = any(target_model in m for m in models)
        if not model_found:
            return {
                'success': True,
                'model_found': False,
                'installed_models': models,
                'message': (
                    f"Đã kết nối thành công tới Ollama Server tại {target_url}, nhưng model '{target_model}' "
                    f"chưa được cài đặt. Vui lòng chạy lệnh: `ollama pull {target_model}` trên máy chủ."
                )
            }
        return {
            'success': True,
            'model_found': True,
            'installed_models': models,
            'message': f"Kết nối Ollama thành công! Model '{target_model}' sẵn sàng hoạt động."
        }
    except requests.exceptions.ConnectionError:
        return {
            'success': False,
            'message': f"Không tìm thấy dịch vụ Ollama đang chạy tại {target_url}. Vui lòng kiểm tra lệnh `ollama serve`."
        }
    except Exception as e:
        return {
            'success': False,
            'message': f"Lỗi kiểm tra kết nối Ollama: {str(e)}"
        }


def generate_ollama_embedding_single(url, model, text):
    """Generate a vector embedding for a single text using Ollama (BAAI/bge-m3 1024-dim)."""
    if not text:
        return None
    target_url = (url or DEFAULT_OLLAMA_URL).rstrip('/')
    target_model = model or DEFAULT_OLLAMA_MODEL

    # First attempt: modern /api/embed endpoint
    try:
        res = requests.post(
            f"{target_url}/api/embed",
            json={'model': target_model, 'input': text},
            timeout=45
        )
        if res.status_code == 200:
            data = res.json()
            embs = data.get('embeddings', [])
            if embs and len(embs) > 0 and len(embs[0]) > 0:
                return json.dumps(embs[0])
    except Exception as e:
        _logger.debug("Ollama /api/embed failed, trying /api/embeddings: %s", str(e))

    # Fallback to legacy /api/embeddings endpoint
    try:
        res = requests.post(
            f"{target_url}/api/embeddings",
            json={'model': target_model, 'prompt': text},
            timeout=45
        )
        if res.status_code == 200:
            data = res.json()
            emb = data.get('embedding', [])
            if emb:
                return json.dumps(emb)
    except Exception as e:
        _logger.warning("Failed to generate embedding via Ollama (%s): %s", target_model, str(e))
    return None


def generate_ollama_embeddings_batch(url, model, texts, batch_size=None, on_batch_success=None):
    """Generate vector embeddings for a list of texts using Ollama with adaptive benchmark sub-batching.
    
    Features:
    - Persistent requests.Session with HTTP Keep-Alive and Connection Pooling.
    - Adaptive Batch Benchmark: Starts with probing batch (16), dynamically scales up to 32-48 if latency < 3s,
      or scales down to 8-16 if latency > 12s / timeout.
    
    Args:
        url: Ollama base url
        model: model name
        texts: list of str
        batch_size: optional fixed batch size (if None, dynamic adaptive sizing is used)
        on_batch_success: callback(batch_indices, batch_results) for incremental DB save
    """
    if not texts:
        return []
    target_url = (url or DEFAULT_OLLAMA_URL).rstrip('/')
    target_model = model or DEFAULT_OLLAMA_MODEL

    # Determine initial batch size: fixed if requested, else adaptive starting at 16
    is_adaptive = batch_size is None or int(batch_size) <= 0
    current_batch_size = 16 if is_adaptive else min(max(int(batch_size), 1), 64)

    results = [None] * len(texts)
    total_texts = len(texts)
    overall_start_time = time.time()
    total_processed = 0
    b_idx = 0

    _logger.info("================================================================================")
    _logger.info(">>> [OLLAMA_EMBEDDING] STARTING ADAPTIVE LOCAL VECTOR EMBEDDING")
    _logger.info("    Model: %s | Server: %s", target_model, target_url)
    _logger.info("    Total chunks: %d | Mode: %s (Initial batch: %d)", total_texts, "Adaptive Benchmark" if is_adaptive else "Fixed", current_batch_size)
    _logger.info("================================================================================")

    # Initialize connection pooling session
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=10, max_retries=1)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    start_idx = 0
    try:
        while start_idx < total_texts:
            b_idx += 1
            effective_batch = min(current_batch_size, total_texts - start_idx)
            sub_texts = texts[start_idx:start_idx + effective_batch]
            sub_indices = list(range(start_idx, start_idx + len(sub_texts)))
            batch_start_time = time.time()
            sub_success = False

            # Adaptive HTTP timeout based on batch size
            batch_timeout = max(60, min(effective_batch * 5, 240))

            # Attempt 1: Call Ollama /api/embed for this sub-batch via pooled session
            try:
                res = session.post(
                    f"{target_url}/api/embed",
                    json={'model': target_model, 'input': sub_texts},
                    timeout=batch_timeout
                )
                if res.status_code == 200:
                    data = res.json()
                    embeddings = data.get('embeddings', [])
                    for i, emb in enumerate(embeddings):
                        if i < len(sub_indices) and emb:
                            results[sub_indices[i]] = json.dumps(emb)
                    sub_success = True
                else:
                    _logger.warning("Ollama /api/embed returned status %d on sub-batch %d (size %d)", res.status_code, b_idx, effective_batch)
            except Exception as e_batch:
                _logger.warning("Ollama sub-batch %d failed (%s), falling back to single items", b_idx, str(e_batch))

            # Fallback to sequential calls for this sub-batch if batch endpoint failed
            if not sub_success:
                for i, text in enumerate(sub_texts):
                    emb = generate_ollama_embedding_single(target_url, target_model, text)
                    results[sub_indices[i]] = emb

            duration = time.time() - batch_start_time
            batch_ok_count = sum(1 for idx in sub_indices if results[idx])
            total_processed += len(sub_texts)
            progress_pct = (total_processed / total_texts) * 100.0

            # Dynamic adaptive scaling for next iteration
            if is_adaptive:
                prev_size = current_batch_size
                if sub_success and duration < 3.0 and current_batch_size < 48:
                    current_batch_size = min(current_batch_size + 16, 48)
                    if current_batch_size != prev_size:
                        _logger.info("    [OLLAMA_ADAPTIVE] Fast response (%.2fs < 3s). Scaled up batch: %d -> %d", duration, prev_size, current_batch_size)
                elif duration > 12.0 or not sub_success:
                    current_batch_size = max(current_batch_size // 2, 8)
                    if current_batch_size != prev_size:
                        _logger.info("    [OLLAMA_ADAPTIVE] High latency / failure (%.2fs > 12s). Scaled down batch: %d -> %d", duration, prev_size, current_batch_size)

            # Calculate ETA
            elapsed_so_far = time.time() - overall_start_time
            avg_per_chunk = elapsed_so_far / total_processed if total_processed > 0 else 0
            remaining_chunks = total_texts - total_processed
            eta_seconds = remaining_chunks * avg_per_chunk
            eta_str = f"{int(eta_seconds // 60)}m {int(eta_seconds % 60):02d}s" if eta_seconds >= 60 else f"{int(eta_seconds)}s"

            _logger.info(
                ">>> [OLLAMA_PROGRESS] Batch %d | Chunks: %d/%d (%.1f%%) | OK: %d/%d in %.2fs (size %d) | ETA: ~%s",
                b_idx, total_processed, total_texts, progress_pct, batch_ok_count, len(sub_texts), duration, effective_batch, eta_str
            )

            # Trigger incremental callback (e.g. database save per batch)
            if on_batch_success:
                try:
                    on_batch_success(sub_indices, [results[idx] for idx in sub_indices])
                except Exception as e_cb:
                    _logger.warning("    [DATABASE_ERROR] Error saving sub-batch %d to DB: %s", b_idx, str(e_cb))

            start_idx += effective_batch

    finally:
        session.close()

    total_time = time.time() - overall_start_time
    total_success = sum(1 for r in results if r)
    _logger.info("================================================================================")
    _logger.info(">>> [OLLAMA_DONE] COMPLETED ALL EMBEDDINGS SUCCESSFULLY!")
    _logger.info("    Success: %d/%d chunks (%.1f%%)", total_success, total_texts, (total_success / total_texts) * 100.0 if total_texts else 0)
    _logger.info("    Total duration: %.2fs (avg %.2fs/chunk)", total_time, (total_time / total_texts) if total_texts else 0)
    _logger.info("================================================================================")

    return results
