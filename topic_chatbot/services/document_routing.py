"""Match document-query routes to the processed content available in a topic."""
import re
import unicodedata

from .sql_engine import _parse_markdown_sheets


def _without_accents(value):
    normalized = unicodedata.normalize('NFD', (value or '').lower())
    return ''.join(char for char in normalized if unicodedata.category(char) != 'Mn').replace('đ', 'd')


def _asks_for_scalar_fact(query):
    """A number used as a fact is not a request to COUNT spreadsheet rows."""
    text = _without_accents(query)
    if not re.search(r'\b(bao nhieu|la gi|la bao nhieu|bang bao nhieu|gia tri nao)\b', text):
        return False
    if re.search(r'\b(tong so|so luong|dem|count|trung binh|average|sum)\b', text):
        return False
    return bool(re.search(
        r'\b(gia tri|khoa|ma|han muc|thoi han|phien ban|tham so|cong|port)\b',
        text,
    ))


def resolve_document_route(route_type, topic, original_query=None):
    """Choose a table route only when a ready document contains a readable table.

    Numerical facts and approval roles also occur in prose. Keywords alone must
    not send those questions to the spreadsheet engine without tabular content.
    This runs before retrieval; actual table-query errors keep their error path.
    """
    if route_type not in ('STRUCTURED_DATA', 'SCHEMA_METADATA'):
        return route_type

    if _asks_for_scalar_fact(original_query):
        return 'SEMANTIC_RAG'

    has_tables = any(
        _parse_markdown_sheets(document.text_content or '')
        for document in topic.document_ids
        if document.state in ('done', 'partial')
    )
    return route_type if has_tables else 'SEMANTIC_RAG'
