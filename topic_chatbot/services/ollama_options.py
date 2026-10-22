"""Explicit context sizing for document-grounded Ollama chat requests."""
DEFAULT_CHAT_CONTEXT_TOKENS = 16384
DEFAULT_CHAT_READ_TIMEOUT = 900


def build_ollama_chat_timeout(read_seconds=None):
    """Allow CPU prompt evaluation without changing or truncating source text."""
    try:
        seconds = int(read_seconds)
    except (TypeError, ValueError):
        seconds = DEFAULT_CHAT_READ_TIMEOUT
    if seconds <= 0:
        seconds = DEFAULT_CHAT_READ_TIMEOUT
    return (10, max(30, min(seconds, 1800)))


def build_ollama_chat_options(context_tokens=None):
    """Reserve a context window for the source text, instructions and answer.

    num_predict limits output only; it does not increase Ollama's input window.
    Administrators may override topic_chatbot.ollama_num_ctx for their hardware.
    """
    try:
        size = int(context_tokens)
    except (TypeError, ValueError):
        size = DEFAULT_CHAT_CONTEXT_TOKENS
    if size <= 0:
        size = DEFAULT_CHAT_CONTEXT_TOKENS
    size = max(4096, min(size, 32768))
    return {'temperature': 0.0, 'num_predict': min(4096, size // 4), 'num_ctx': size}
