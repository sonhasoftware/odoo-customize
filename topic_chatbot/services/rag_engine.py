# -*- coding: utf-8 -*-
import json
import logging
import math
import re
import requests
from odoo.http import request
from .query_rewriter import should_use_hyde, generate_hypothetical_document
from ..utils.security_utils import normalize_model_name

_logger = logging.getLogger(__name__)

def _retrieve_schema_metadata(env, topic, message, original_query=None):
    """Retrieve Sheet Summary / Schema chunks for SCHEMA_METADATA route and return early.
    Guarantees Invariant 2: No Tier 1, Tier 2, or Tier 3 RAG called."""
    schema_chunks = []
    try:
        env.cr.execute("""
            SELECT c.id, c.content, c.sequence, c.document_id, d.name
              FROM topic_chatbot_chunk c
              JOIN topic_chatbot_document d ON d.id = c.document_id
             WHERE c.topic_id = %s
               AND d.state IN ('done', 'partial')
               AND (c.content LIKE '%%[SHEET_SUMMARY_SCHEMA]%%' OR c.content LIKE '%%Các cột trong bảng:%%')
             ORDER BY c.document_id, c.sequence
             LIMIT 10
        """, (topic.id,))
        for s_row in env.cr.fetchall():
            schema_chunks.append({
                'id': s_row[0],
                'content': s_row[1],
                'sequence': s_row[2],
                'document_id': s_row[3],
                'document_name': s_row[4],
                'score': 2.0,
                'topic_name': topic.name or '',
                'route_type': 'SCHEMA_METADATA'
            })
        _logger.info("[SCHEMA_ROUTER] Route 'SCHEMA_METADATA' retrieved %d Sheet Summary / Schema chunks. Early return.", len(schema_chunks))
    except Exception as e_sc:
        _logger.error("[SCHEMA_ROUTER_ERROR] Failed querying sheet summary chunks: %s", str(e_sc))
    return schema_chunks


def _retrieve_structured_data(env, topic, message, filters=None, original_query=None, structured_query=None, max_limit=100):
    """Execute Structured Table Query for STRUCTURED_DATA route and return early.
    Guarantees Invariant 1: No Tier 1, Tier 2, or Tier 3 RAG called.
    Guarantees Invariant 4: No silent fallback to semantic RAG on failure."""
    from .sql_engine import execute_structured_query_object
    from .query_rewriter import parse_to_structured_query_object

    query_text = original_query or message

    # Parse into Structured Query Object
    if isinstance(structured_query, dict):
        query_obj = structured_query
    else:
        query_obj = parse_to_structured_query_object(structured_query or query_text)

    # Execute Safe Table Query
    res = execute_structured_query_object(env, topic, query_obj, max_limit=max_limit)

    if res.get('success'):
        q_type = res.get('query_type', 'LIST')
        res_count = res.get('result_count', 0)
        ret_count = res.get('returned_count', 0)
        truncated = res.get('truncated', False)
        sheet = res.get('sheet') or 'Toàn bộ bảng'
        flt_desc = json.dumps(res.get('filters', []), ensure_ascii=False)
        cols = res.get('columns', [])
        rows = res.get('rows', [])

        # Build clean Markdown representation of the structured result
        md_lines = [
            f"[STRUCTURED_QUERY_RESULT]",
            f"- Loại truy vấn: {q_type}",
            f"- Bảng / Sheet: {sheet}",
            f"- Điều kiện lọc: {flt_desc}",
            f"- Tổng số dòng khớp: {res_count} (Trả về: {ret_count}, Cắt bớt: {truncated})",
            ""
        ]

        raci = res.get('raci_summary')
        if raci:
            md_lines.append("THÔNG TIN PHÂN QUYỀN (RACI):")
            if raci.get('approvers'):
                md_lines.append(f"- Người / Chức danh PHÊ DUYỆT (A): {', '.join(raci['approvers'])}")
            if raci.get('responsible'):
                md_lines.append(f"- Người / Chức danh SOÁT XÉT / CHỊU TRÁCH NHIỆM (R): {', '.join(raci['responsible'])}")
            if raci.get('proposers'):
                md_lines.append(f"- Người / Chức danh ĐỀ XUẤT / TRÌNH DUYỆT (P): {', '.join(raci['proposers'])}")
            if raci.get('informed'):
                md_lines.append(f"- Người / Chức danh NHẬN THÔNG BÁO (I): {', '.join(raci['informed'])}")
            md_lines.append("")

        if rows and cols:
            md_lines.append("| " + " | ".join(cols) + " |")
            md_lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
            for r in rows:
                row_vals = [str(r.get(c, '')).replace('\n', ' ').strip() for c in cols]
                md_lines.append("| " + " | ".join(row_vals) + " |")
        elif res_count == 0:
            md_lines.append("-> Kết quả: Không tìm thấy bản ghi nào thỏa mãn điều kiện.")

        content = "\n".join(md_lines)
        _logger.info("[SQ_DEBUG][CONTEXT]\nstructured_result =\n%s", content)
        return [{
            'id': 0,
            'topic_name': topic.name or '',
            'document_name': f"Bảng dữ liệu: {sheet}",
            'sequence': 1,
            'chunk_type': 'structured_result',
            'route_type': 'STRUCTURED_DATA',
            'content': content,
            'score': 5.0,
            'structured_data': res
        }]
    else:
        # Error case - MUST NOT silent fallback to Tier 3!
        err_msg = res.get('error', 'Lỗi không xác định khi thực thi truy vấn bảng có cấu trúc')
        _logger.error("[STRUCTURED_QUERY_ERROR] Execution failed: %s", err_msg)
        return [{
            'id': 0,
            'topic_name': topic.name or '',
            'document_name': "Lỗi truy vấn",
            'sequence': 1,
            'chunk_type': 'structured_result',
            'route_type': 'STRUCTURED_DATA',
            'content': f"[STRUCTURED_QUERY_ERROR] Lỗi thực thi truy vấn bảng dữ liệu: {err_msg}",
            'score': 0.0,
            'structured_data': res
        }]


def retrieve_context(env, topic_id, message, limit=15, filters=None, original_query=None, is_valid=True, route_type='SEMANTIC_RAG', structured_query=None):
    """Retrieve relevant chunks using True Hybrid Search with Reciprocal Rank Fusion (RRF, k=60),
    Selective HyDE for abstract queries, Metadata Filtering, and Intent Routing (SCHEMA_METADATA, STRUCTURED_DATA)."""
    if env is None:
        try:
            from odoo.http import request
            env = env
        except Exception:
            return []

    import json
    import math
    import re

    query_text = original_query or message

    # Relevance Gate: Nếu query bị đánh giá là off-topic/nonsense/copied text rác, bỏ qua retrieval
    if is_valid is False:
        _logger.info("[RELEVANCE_GATE] Query '%s' marked as is_valid=False. Dropping context retrieval.", query_text[:60].replace('\n', ' '))
        return []

    try:
        topic_id_int = int(topic_id)
    except (ValueError, TypeError):
        return []

    # Verify topic access first using ORM search (applying record rules automatically)
    topic = env['topic_chatbot.topic'].search([('id', '=', topic_id_int)])
    if not topic:
        return []

    # Clean message check
    cleaned_msg = message.strip()
    if not cleaned_msg:
        return []

    # ROUTE ISOLATION (Sections 19, 20, 21):
    # Invariant 2: SCHEMA_METADATA -> Early return schema metadata chunks
    if route_type == 'SCHEMA_METADATA':
        _logger.info("[SCHEMA_ROUTER] Route 'SCHEMA_METADATA' activated. Fetching schema chunks only (Invariant 2).")
        schema_res = _retrieve_schema_metadata(env, topic, message, original_query=query_text)
        for c in schema_res:
            c['tier_activated'] = 'Schema Metadata Route'
            c['tier_reason'] = 'route_type == SCHEMA_METADATA'
            c['retrieval_method'] = 'schema_summary_chunks'
        return schema_res

    # Invariant 1: STRUCTURED_DATA -> Early return structured query result
    if route_type == 'STRUCTURED_DATA':
        _logger.info("[STRUCTURED_ROUTER] Route 'STRUCTURED_DATA' activated. Executing Safe Table Query only (Invariant 1).")
        struct_res = _retrieve_structured_data(
            env, topic, message,
            filters=filters,
            original_query=query_text,
            structured_query=structured_query,
            max_limit=100
        )
        for c in struct_res:
            c['tier_activated'] = 'Structured Table Data Route'
            c['tier_reason'] = 'route_type == STRUCTURED_DATA'
            c['retrieval_method'] = 'sql_engine_table_query'
        return struct_res

    # Invariant 3: SEMANTIC_RAG -> Continues down to Tier 1, Tier 2, Tier 3 hybrid search
    _logger.info("[SEMANTIC_ROUTER] Route 'SEMANTIC_RAG' activated. Entering semantic retrieval pipeline (Invariant 3).")

    query_text = original_query or message
    retrieval_method = "fts_fallback"
    fallback_reason = None
    vector_call_succeeded = False

    params = env['ir.config_parameter'].sudo()
    api_key = params.get_param('topic_chatbot.gemini_api_key')
    embedding_model = params.get_param('topic_chatbot.embedding_model', default='gemini-embedding-2') or 'gemini-embedding-2'

    # Build Metadata Filter SQL clauses (Whitelisted & Parameterized)
    filter_sql = ""
    filter_params = []
    if filters:
        if filters.get('apply_year'):
            try:
                filter_sql += " AND d.apply_year = %s"
                filter_params.append(int(filters['apply_year']))
            except (ValueError, TypeError):
                pass
        if filters.get('doc_type') and filters['doc_type'] in ('regulation', 'process', 'report', 'form', 'manual', 'other'):
            filter_sql += " AND d.doc_type = %s"
            filter_params.append(filters['doc_type'])
        if filters.get('department') and isinstance(filters['department'], str):
            dept_clean = filters['department'].strip()
            if dept_clean:
                filter_sql += " AND d.department ILIKE %s"
                filter_params.append(f"%{dept_clean}%")

    # Check topic documents for Tier 1 / Tier 2
    # Filter: state IN ('done', 'partial')
    doc_sql = f"""
        SELECT d.id, d.name, d.text_content, COALESCE(d.content_length, LENGTH(d.text_content)) AS content_length
          FROM topic_chatbot_document d
         WHERE d.topic_id = %s
           AND d.state IN ('done', 'partial')
           AND d.text_content IS NOT NULL
           AND LENGTH(TRIM(d.text_content)) > 10
           {filter_sql}
         ORDER BY d.id ASC
    """
    env.cr.execute(doc_sql, [topic.id] + filter_params)
    all_topic_docs = env.cr.fetchall()

    # FALLBACK: Nếu metadata filter từ LLM loại hết document → retry bỏ filter
    if not all_topic_docs and filter_sql:
        _logger.warning(
            "[RAG_DEBUG][FILTER_FALLBACK] Metadata filters eliminated all documents. "
            "Retrying without filters. Original filter_sql: '%s', filter_params: %s",
            filter_sql, filter_params
        )
        filter_sql = ""
        filter_params = []
        doc_sql_no_filter = """
            SELECT d.id, d.name, d.text_content,
                   COALESCE(d.content_length, LENGTH(d.text_content)) AS content_length
              FROM topic_chatbot_document d
             WHERE d.topic_id = %s
               AND d.state IN ('done', 'partial')
               AND d.text_content IS NOT NULL
               AND LENGTH(TRIM(d.text_content)) > 10
             ORDER BY d.id ASC
        """
        env.cr.execute(doc_sql_no_filter, [topic.id])
        all_topic_docs = env.cr.fetchall()

    if all_topic_docs:
        total_topic_chars = sum(row[3] or len(row[2] or '') for row in all_topic_docs)

        # Log all documents in topic for debugging
        for d_row in all_topic_docs:
            d_id, d_name, d_text, d_len = d_row[:4]
            d_chunk_count = 0
            try:
                env.cr.execute("SELECT COUNT(*) FROM topic_chatbot_chunk WHERE document_id = %s", [d_id])
                c_res = env.cr.fetchone()
                d_chunk_count = c_res[0] if c_res else 0
            except Exception:
                d_chunk_count = -1
            _logger.info(
                "[RAG_DEBUG][DOC]\n"
                "  - document_id: %s\n"
                "  - document_name: '%s'\n"
                "  - state: done/partial\n"
                "  - content_length: %s\n"
                "  - chunk_count: %s",
                d_id, d_name, d_len, d_chunk_count
            )

        # ========== TẦNG 1: Whole-Topic Direct Injection (Topic nhỏ <= 25000 ký tự) ==========
        if total_topic_chars <= 25000:
            _logger.info(
                "[RAG_DEBUG][TIER]\n"
                "  - topic_id: %s\n"
                "  - topic_name: '%s'\n"
                "  - document_count: %d\n"
                "  - total_topic_chars: %d\n"
                "  - threshold_tier1: 25000\n"
                "  - selected_tier: Tier 1 (Whole-Topic Direct Injection)\n"
                "  - tier_reason: 'total_topic_chars (%d) <= 25000'",
                topic.id, topic.name or '', len(all_topic_docs), total_topic_chars, total_topic_chars
            )
            _logger.info(
                "[TIERED_RETRIEVAL] Tier 1 (Whole-Topic) activated: topic_id=%s, total_docs=%d, total_chars=%d <= 25000. Skipping chunk search.",
                topic.id, len(all_topic_docs), total_topic_chars
            )
            full_content_parts = []
            for d_id, d_name, d_text, d_len in all_topic_docs:
                full_content_parts.append(f"=== Tài liệu: {d_name} ===\n{d_text.strip()}")
            combined_text = "\n\n".join(full_content_parts)

            _logger.info(
                "[RETRIEVAL_RESULT]\n"
                "  - retrieval_method: tiered_whole_topic\n"
                "  - fallback_reason: None (Tier 1 Whole-Topic Injection)\n"
                "  - query_text: '%s'\n"
                "  - total_retrieved: 1\n"
                "  - chunks: %s",
                query_text,
                json.dumps([{
                    'id': 0,
                    'score': 1.0,
                    'preview_50': combined_text[:50].replace('\n', ' ')
                }], ensure_ascii=False)
            )

            return [{
                'id': 0,
                'content': combined_text,
                'sequence': 1,
                'document_id': 0,
                'document_name': 'Tổng hợp từ toàn bộ tài liệu trong topic',
                'score': 1.0,
                'topic_name': topic.name or '',
                'tier_activated': 'Tier 1 (Whole-Topic Direct Injection)',
                'tier_reason': f'total_topic_chars ({total_topic_chars}) <= 25000',
                'retrieval_method': 'tiered_whole_topic',
            }]

        # ========== TẦNG 2: Document-Level Retrieval (Topic vừa/lớn, Docs nhỏ) ==========
        # Check if any individual documents are eligible (content_length <= 20000)
        eligible_docs = [row for row in all_topic_docs if (row[3] or len(row[2] or '')) <= 20000]
        if eligible_docs:
            try:
                fts_query_str = cleaned_msg.strip()
                tier2_sql = f"""
                    SELECT d.id, d.name, d.text_content, COALESCE(d.content_length, LENGTH(d.text_content)) AS content_length,
                           ts_rank_cd(to_tsvector('simple', d.text_content), plainto_tsquery('simple', %s)) AS rank
                      FROM topic_chatbot_document d
                     WHERE d.topic_id = %s
                       AND d.state IN ('done', 'partial')
                       AND d.text_content IS NOT NULL
                       AND COALESCE(d.content_length, LENGTH(d.text_content)) <= 20000
                       AND to_tsvector('simple', d.text_content) @@ plainto_tsquery('simple', %s)
                       {filter_sql}
                  ORDER BY rank DESC
                     LIMIT 5
                """
                tier2_params = [fts_query_str, topic.id, fts_query_str] + filter_params
                env.cr.execute(tier2_sql, tier2_params)
                tier2_ranked = env.cr.fetchall()

                if tier2_ranked:
                    selected_docs = []
                    accumulated_chars = 0
                    TIER2_MAX_TOTAL = 50000
                    TIER2_MAX_DOCS = 3

                    for d_id, d_name, d_text, d_len, rank_score in tier2_ranked:
                        cur_len = d_len or len(d_text or '')
                        if accumulated_chars + cur_len > TIER2_MAX_TOTAL:
                            break  # Hard budget limit: DỪNG THÊM DOCUMENT, không cắt giữa chừng document
                        selected_docs.append({
                            'id': d_id,
                            'name': d_name,
                            'text': d_text,
                            'length': cur_len,
                            'rank': float(rank_score) if rank_score else 0.0,
                        })
                        accumulated_chars += cur_len
                        if len(selected_docs) >= TIER2_MAX_DOCS:
                            break

                    if selected_docs:
                        _logger.info(
                            "[RAG_DEBUG][TIER]\n"
                            "  - topic_id: %s\n"
                            "  - topic_name: '%s'\n"
                            "  - document_count: %d\n"
                            "  - total_topic_chars: %d\n"
                            "  - threshold_tier1: 25000\n"
                            "  - selected_tier: Tier 2 (Document-Level Retrieval)\n"
                            "  - tier_reason: 'total_topic_chars (%d) > 25000 and %d eligible docs matched FTS query'",
                            topic.id, topic.name or '', len(all_topic_docs), total_topic_chars, total_topic_chars, len(selected_docs)
                        )
                        _logger.info(
                            "[TIERED_RETRIEVAL] Tier 2 (Document-Level) activated: topic_id=%s, matched_docs=%d, total_chars=%d. Injecting full document texts.",
                            topic.id, len(selected_docs), accumulated_chars
                        )
                        tier2_result = [
                            {
                                'id': d['id'],
                                'content': d['text'].strip(),
                                'sequence': 1,
                                'document_id': d['id'],
                                'document_name': d['name'] or 'Unknown Document',
                                'score': round(d['rank'], 5),
                                'topic_name': topic.name or '',
                                'tier_activated': 'Tier 2 (Document-Level Retrieval)',
                                'tier_reason': f'total_topic_chars ({total_topic_chars}) > 25000 and {len(selected_docs)} eligible docs matched FTS query',
                                'retrieval_method': 'tiered_document_level',
                            }
                            for d in selected_docs
                        ]

                        _logger.info(
                            "[RETRIEVAL_RESULT]\n"
                            "  - retrieval_method: tiered_document_level\n"
                            "  - fallback_reason: None (Tier 2 Document-Level Retrieval)\n"
                            "  - query_text: '%s'\n"
                            "  - total_retrieved: %d\n"
                            "  - chunks: %s",
                            query_text,
                            len(tier2_result),
                            json.dumps([
                                {
                                    'id': c['id'],
                                    'score': c['score'],
                                    'preview_50': c['content'][:50].replace('\n', ' ')
                                }
                                for c in tier2_result
                            ], ensure_ascii=False)
                        )
                        return tier2_result
            except Exception as e:
                _logger.warning("Tier 2 document-level search error (falling back to Tier 3): %s", str(e))

    # ========== TẦNG 3: Chunk-Level Hybrid Search (Fallback cho Topic lớn / Document lớn) ==========
    _logger.info(
        "[RAG_DEBUG][TIER]\n"
        "  - topic_id: %s\n"
        "  - topic_name: '%s'\n"
        "  - document_count: %d\n"
        "  - total_topic_chars: %d\n"
        "  - threshold_tier1: 25000\n"
        "  - selected_tier: Tier 3 (Chunk-Level Hybrid Search)\n"
        "  - tier_reason: 'total_topic_chars > 25000 and Tier 2 did not match'",
        topic.id, topic.name or '', len(all_topic_docs) if 'all_topic_docs' in locals() and all_topic_docs else 0,
        total_topic_chars if 'total_topic_chars' in locals() else 0
    )
    _logger.info("[TIERED_RETRIEVAL] Tier 3 (Chunk-Level Hybrid Search) activated for topic_id=%s", topic.id)

    chunk_info_map = {}   # chunk_id -> chunk dict
    vector_ranked_list = []  # list of chunk_ids
    fts_ranked_list = []     # list of chunk_ids
    phrase_ranked_list = []  # list of chunk_ids

    # 1. PgVector Semantic Search (Dual-Vector & Dual-Mode: Gemini vs 100% Local Ollama)
    from . import embedding_service
    emb_cfg = embedding_service.get_embedding_config(env)
    active_provider = emb_cfg['provider']

    query_emb_json = None
    target_vector_column = 'embedding_vector'
    emb_text = cleaned_msg

    if active_provider == 'ollama':
        # CHẾ ĐỘ 2: 100% LOCAL OLLAMA ONLY (HOÀN TOÀN KHÔNG GỌI GEMINI)
        target_vector_column = 'embedding_vector_ollama'
        try:
            query_emb_json = embedding_service.generate_ollama_embedding_single(
                emb_cfg['ollama_url'], emb_cfg['ollama_model'], emb_text
            )
            if query_emb_json:
                retrieval_method = "ollama_embedding"
            else:
                fallback_reason = f"Ollama Local Server tại {emb_cfg['ollama_url']} không phản hồi hoặc chưa pull model {emb_cfg['ollama_model']}"
                retrieval_method = "fts_fallback"
        except Exception as e_ollama:
            fallback_reason = f"Lỗi kết nối Ollama Local: {str(e_ollama)}"
            retrieval_method = "fts_fallback"
    else:
        # CHẾ ĐỘ 1: GEMINI VỚI OLLAMA AUTO-FALLBACK KHI HẾT QUOTA
        target_vector_column = 'embedding_vector'
        if not api_key:
            # Nếu chưa có Gemini API Key, thử Ollama fallback nếu server đang chạy
            if emb_cfg.get('ollama_url'):
                try:
                    query_emb_json = embedding_service.generate_ollama_embedding_single(
                        emb_cfg['ollama_url'], emb_cfg['ollama_model'], emb_text
                    )
                    if query_emb_json:
                        target_vector_column = 'embedding_vector_ollama'
                        retrieval_method = "ollama_fallback_embedding"
                except Exception:
                    pass
            if not query_emb_json:
                fallback_reason = "Gemini API Key is not configured in settings"
                retrieval_method = "fts_fallback"
        else:
            try:
                if should_use_hyde(cleaned_msg):
                    hyde_doc = generate_hypothetical_document(env, cleaned_msg, api_key, model=embedding_model)
                    if hyde_doc and len(hyde_doc.strip()) > 20:
                        emb_text = hyde_doc
                        _logger.info("Selective HyDE activated for abstract query: '%s' -> Excerpt: '%s...'", cleaned_msg, hyde_doc[:80].replace('\n', ' '))

                # Thử sinh vector bằng Gemini
                query_emb_json = env['topic_chatbot.chunk']._generate_embedding(
                    emb_text, api_key, embedding_model, provider='gemini'
                )
                if query_emb_json:
                    target_vector_column = 'embedding_vector'
                    retrieval_method = "gemini_embedding"
                else:
                    # Gemini thất bại (429 quota, timeout...) -> AUTO-FALLBACK SANG OLLAMA
                    _logger.warning("Gemini embedding returned None (possible 429 quota). Attempting Auto-Fallback to Ollama...")
                    if emb_cfg.get('ollama_url'):
                        query_emb_json = embedding_service.generate_ollama_embedding_single(
                            emb_cfg['ollama_url'], emb_cfg['ollama_model'], cleaned_msg
                        )
                        if query_emb_json:
                            target_vector_column = 'embedding_vector_ollama'
                            retrieval_method = "ollama_fallback_embedding"
                            _logger.info("Auto-Fallback to Ollama Vector Search succeeded on column embedding_vector_ollama.")
            except Exception as e:
                err_msg = str(e)
                if api_key:
                    err_msg = err_msg.replace(api_key, "REDACTED")
                _logger.warning("Gemini embedding failed (%s). Attempting Auto-Fallback to Ollama...", err_msg)
                if emb_cfg.get('ollama_url'):
                    try:
                        query_emb_json = embedding_service.generate_ollama_embedding_single(
                            emb_cfg['ollama_url'], emb_cfg['ollama_model'], cleaned_msg
                        )
                        if query_emb_json:
                            target_vector_column = 'embedding_vector_ollama'
                            retrieval_method = "ollama_fallback_embedding"
                    except Exception as e_fb:
                        _logger.warning("Auto-fallback to Ollama also failed: %s", str(e_fb))

    # Thực thi truy vấn PgVector nếu có vector hợp lệ
    if query_emb_json:
        try:
            env.cr.execute("SET LOCAL hnsw.ef_search = 40;")
            sql_query = f"""
                SELECT c.id, c.content, c.sequence, c.document_id, d.name,
                       c.parent_id, p.content AS parent_content, p.sequence AS parent_sequence,
                       c.{target_vector_column} <=> %s::vector AS distance
                  FROM topic_chatbot_chunk c
                  JOIN topic_chatbot_document d ON d.id = c.document_id
                  LEFT JOIN topic_chatbot_chunk p ON p.id = c.parent_id
                 WHERE c.topic_id = %s 
                    AND c.{target_vector_column} IS NOT NULL
                    AND (c.chunk_type IN ('child', 'standard') OR c.chunk_type IS NULL)
                    {filter_sql}
               ORDER BY c.{target_vector_column} <=> %s::vector
                  LIMIT %s
            """
            exec_params = [query_emb_json, topic.id] + filter_params + [query_emb_json, limit]
            env.cr.execute(sql_query, exec_params)
            rows = env.cr.fetchall()

            for row in rows:
                chunk_id, content, sequence, doc_id, doc_name, parent_id, parent_content, parent_seq, distance = row
                sim = 1.0 - float(distance)
                if sim >= 0.18:  # Correlation threshold
                    if chunk_id not in chunk_info_map:
                        chunk_info_map[chunk_id] = {
                            'id': chunk_id,
                            'content': content,
                            'sequence': sequence or 1,
                            'document_id': doc_id,
                            'document_name': doc_name or 'Unknown Document',
                            'parent_id': parent_id,
                            'parent_content': parent_content,
                            'parent_sequence': parent_seq,
                            'sim': sim,
                        }
                    else:
                        chunk_info_map[chunk_id]['sim'] = sim
                    vector_ranked_list.append(chunk_id)

            vector_call_succeeded = True
            _logger.info(
                "[RETRIEVAL_DECISION] Decision Point: retrieval_method='%s', vector_column='%s', fallback_reason=None, vector_matches=%d, query_text='%s'",
                retrieval_method, target_vector_column, len(vector_ranked_list), query_text
            )
            _logger.info(
                "[RAG_DEBUG][VECTOR]\n"
                "  - rewritten_query: '%s'\n"
                "  - query_embedding_generated: True\n"
                "  - vector_column: '%s'\n"
                "  - result_count: %d\n"
                "  - top_10: %s",
                emb_text, target_vector_column, len(vector_ranked_list),
                json.dumps([
                    {
                        'chunk_id': c_id,
                        'document_id': chunk_info_map[c_id]['document_id'],
                        'parent_id': chunk_info_map[c_id]['parent_id'],
                        'similarity': round(chunk_info_map[c_id].get('sim', 0.0), 5),
                        'sequence': chunk_info_map[c_id]['sequence'],
                        'preview_150_200': chunk_info_map[c_id]['content'][:200].replace('\n', ' ')
                    }
                    for c_id in vector_ranked_list[:10]
                ], ensure_ascii=False, indent=2)
            )
        except Exception as e_sql:
            err_msg = str(e_sql)
            fallback_reason = f"PgVector query error on {target_vector_column}: {err_msg}"
            retrieval_method = "fts_fallback"
            _logger.warning("[RAG_DEBUG][VECTOR_ERROR] Failed querying pgvector on column %s: %s", target_vector_column, err_msg)
    else:
        if not fallback_reason:
            fallback_reason = "No vector embedding generated (possible rate limit 429, timeout, or model error)"
        retrieval_method = "fts_fallback"
        _logger.info(
            "[RETRIEVAL_DECISION] Decision Point: retrieval_method='%s', fallback_reason='%s', query_text='%s'",
            retrieval_method, fallback_reason, query_text
        )
        _logger.warning(
            "[RAG_DEBUG][VECTOR]\n"
            "  - rewritten_query: '%s'\n"
            "  - query_embedding_generated: False\n"
            "  - result_count: 0\n"
            "  - top_10: []",
            emb_text
        )

    # 2. Extract Keyphrases and Meaningful Words for Intent-Aware Retrieval
    STOP_WORDS = {
        'xin', 'chào', 'hello', 'hi', 'hey', 'tôi', 'bạn', 'này', 'cái', 'cho',
        'hỏi', 'là', 'và', 'có', 'không', 'ở', 'trong', 'được', 'người', 'những',
        'các', 'như', 'bot', 'ad', 'admin', 'ai', 'chỉ', 'giúp', 'với', 'ạ',
        'gì', 'nào', 'đâu', 'sao', 'thế', 'nếu', 'thì', 'mà', 'của', 'để', 'từ',
        'một', '1', 'hai', '2', 'ba', '3', 'bốn', '4', 'năm', '5'
    }
    custom_stop_words = params.get_param('topic_chatbot.stop_words', '')
    if custom_stop_words:
        for w in custom_stop_words.split(','):
            w_clean = w.strip().lower()
            if w_clean:
                STOP_WORDS.add(w_clean)

    raw_words = [w for w in re.sub(r'[^\w\s]', ' ', cleaned_msg.lower()).split() if w]
    meaningful_words = [w for w in raw_words if w not in STOP_WORDS and len(w) > 1]

    # Extract 2-gram, 3-gram, 4-gram keyphrases
    keyphrases = []
    for n in (4, 3, 2):
        for i in range(len(raw_words) - n + 1):
            phrase_tokens = raw_words[i:i + n]
            if any(t not in STOP_WORDS for t in phrase_tokens):
                phrase_str = " ".join(phrase_tokens).strip()
                if len(phrase_str) >= 4 and phrase_str not in keyphrases:
                    keyphrases.append(phrase_str)

    _logger.info(
        "[RAG_DEBUG][QUERY_EXTRACTED_WORDS]\n"
        "  - extracted_keyphrases: %s\n"
        "  - meaningful_words: %s",
        keyphrases, meaningful_words
    )

    # 2a. Postgres tsvector FTS (Flexible Multi-Phrase Query on Child & Standard chunks)
    tsquery_expr = ""
    if keyphrases or meaningful_words:
        try:
            fts_query_parts = []
            for kp in keyphrases[:5]:
                kp_tokens = [t for t in kp.split() if t not in STOP_WORDS]
                if kp_tokens:
                    fts_query_parts.append(" & ".join(kp_tokens))
            if meaningful_words:
                fts_query_parts.append(" & ".join(meaningful_words[:4]))

            if fts_query_parts:
                tsquery_expr = " | ".join(fts_query_parts)
                sql_fts = f"""
                    SELECT c.id, c.content, c.sequence, c.document_id, d.name,
                           c.parent_id, p.content AS parent_content, p.sequence AS parent_sequence,
                           ts_rank_cd(to_tsvector('simple', c.content), to_tsquery('simple', %s)) AS rank
                      FROM topic_chatbot_chunk c
                      JOIN topic_chatbot_document d ON d.id = c.document_id
                      LEFT JOIN topic_chatbot_chunk p ON p.id = c.parent_id
                     WHERE c.topic_id = %s
                       AND (c.chunk_type IN ('child', 'standard') OR c.chunk_type IS NULL)
                       {filter_sql}
                       AND to_tsvector('simple', c.content) @@ to_tsquery('simple', %s)
                  ORDER BY rank DESC
                     LIMIT %s
                """
                exec_fts_params = [tsquery_expr, topic.id] + filter_params + [tsquery_expr, limit]
                env.cr.execute(sql_fts, exec_fts_params)
                for row in env.cr.fetchall():
                    c_id, content, sequence, doc_id, doc_name, parent_id, parent_content, parent_seq, rank = row
                    if c_id not in chunk_info_map:
                        chunk_info_map[c_id] = {
                            'id': c_id,
                            'content': content,
                            'sequence': sequence or 1,
                            'document_id': doc_id,
                            'document_name': doc_name or 'Unknown Document',
                            'parent_id': parent_id,
                            'parent_content': parent_content,
                            'parent_sequence': parent_seq,
                            'fts_rank_val': float(rank) if rank else 0.0,
                        }
                    else:
                        chunk_info_map[c_id]['fts_rank_val'] = float(rank) if rank else 0.0
                    fts_ranked_list.append(c_id)

                _logger.info(
                    "[RAG_DEBUG][FTS]\n"
                    "  - generated_tsquery: '%s'\n"
                    "  - result_count: %d\n"
                    "  - top_10: %s",
                    tsquery_expr, len(fts_ranked_list),
                    json.dumps([
                        {
                            'chunk_id': c_id,
                            'document_id': chunk_info_map[c_id]['document_id'],
                            'parent_id': chunk_info_map[c_id]['parent_id'],
                            'rank': round(chunk_info_map[c_id].get('fts_rank_val', 0.0), 5),
                            'sequence': chunk_info_map[c_id]['sequence'],
                            'preview_150_200': chunk_info_map[c_id]['content'][:200].replace('\n', ' ')
                        }
                        for c_id in fts_ranked_list[:10]
                    ], ensure_ascii=False, indent=2)
                )
        except Exception as e:
            _logger.debug("FTS search query skipped or failed: %s", str(e))
            _logger.warning("[RAG_DEBUG][FTS_ERROR] FTS search query error: %s", str(e))

    # 2b. Exact Keyphrase & Keyword ILIKE Matching
    def escape_like(s):
        return s.replace('=', '==').replace('%', '=%').replace('_', '=_')

    all_search_terms = list(keyphrases[:8]) + [w for w in meaningful_words if w not in keyphrases]
    if all_search_terms:
        try:
            escaped_terms = [escape_like(t) for t in all_search_terms]
            like_clauses = " OR ".join(["c.content ILIKE %s ESCAPE '='"] * len(escaped_terms))
            sql_like = f"""
                SELECT c.id, c.content, c.sequence, c.document_id, d.name,
                       c.parent_id, p.content AS parent_content, p.sequence AS parent_sequence
                  FROM topic_chatbot_chunk c
                  JOIN topic_chatbot_document d ON d.id = c.document_id
                  LEFT JOIN topic_chatbot_chunk p ON p.id = c.parent_id
                 WHERE c.topic_id = %s 
                   AND (c.chunk_type IN ('child', 'standard') OR c.chunk_type IS NULL)
                   {filter_sql}
                   AND ({like_clauses})
                 LIMIT 60
            """
            params_sql = [topic.id] + filter_params + [f"%{term}%" for term in escaped_terms]
            env.cr.execute(sql_like, params_sql)
            phrase_matches = []
            for row in env.cr.fetchall():
                c_id, content, sequence, doc_id, doc_name, parent_id, parent_content, parent_seq = row
                content_lower = content.lower()
                
                matched_kp_count = sum(1 for kp in keyphrases[:6] if kp in content_lower)
                word_match_count = sum(content_lower.count(w) for w in meaningful_words)
                
                if matched_kp_count > 0 or word_match_count > 0:
                    if c_id not in chunk_info_map:
                        chunk_info_map[c_id] = {
                            'id': c_id,
                            'content': content,
                            'sequence': sequence or 1,
                            'document_id': doc_id,
                            'document_name': doc_name or 'Unknown Document',
                            'parent_id': parent_id,
                            'parent_content': parent_content,
                            'parent_sequence': parent_seq,
                            'matched_kp_count': matched_kp_count,
                            'word_match_count': word_match_count,
                        }
                    else:
                        chunk_info_map[c_id]['matched_kp_count'] = matched_kp_count
                        chunk_info_map[c_id]['word_match_count'] = word_match_count
                    phrase_matches.append((c_id, matched_kp_count, word_match_count))
            
            # Sort ILIKE matches by phrase match count DESC, then word count DESC
            phrase_matches.sort(key=lambda x: (x[1], x[2]), reverse=True)
            phrase_ranked_list = [item[0] for item in phrase_matches]

            _logger.info(
                "[RAG_DEBUG][ILIKE]\n"
                "  - keyphrases: %s\n"
                "  - meaningful_words: %s\n"
                "  - result_count: %d\n"
                "  - top_10: %s",
                keyphrases, meaningful_words, len(phrase_ranked_list),
                json.dumps([
                    {
                        'chunk_id': c_id,
                        'document_id': chunk_info_map[c_id]['document_id'],
                        'parent_id': chunk_info_map[c_id]['parent_id'],
                        'matched_kp_count': chunk_info_map[c_id].get('matched_kp_count', 0),
                        'word_match_count': chunk_info_map[c_id].get('word_match_count', 0),
                        'sequence': chunk_info_map[c_id]['sequence'],
                        'preview_150_200': chunk_info_map[c_id]['content'][:200].replace('\n', ' ')
                    }
                    for c_id in phrase_ranked_list[:10]
                ], ensure_ascii=False, indent=2)
            )
        except Exception as e:
            _logger.debug("ILIKE fallback search skipped or failed: %s", str(e))
            _logger.warning("[RAG_DEBUG][ILIKE_ERROR] ILIKE search error: %s", str(e))

    if not chunk_info_map:
        _logger.info(
            "[RETRIEVAL_RESULT]\n"
            "  - retrieval_method: %s\n"
            "  - fallback_reason: %s\n"
            "  - query_text: '%s'\n"
            "  - total_retrieved: 0\n"
            "  - chunks: []",
            retrieval_method,
            fallback_reason if fallback_reason else "No matching chunks found in topic",
            query_text
        )
        return []

    # 3. Reciprocal Rank Fusion (RRF) Calculation (k = 60)
    RRF_K = 60.0
    rrf_scores = {}
    rank_breakdowns = {}

    # 3a. Add scores from Vector Search
    for rank, c_id in enumerate(vector_ranked_list, start=1):
        rrf_contrib = 1.0 / (RRF_K + rank)
        rrf_scores[c_id] = rrf_scores.get(c_id, 0.0) + rrf_contrib
        rank_breakdowns.setdefault(c_id, {})['vec_rank'] = rank

    # 3b. Add scores from Full-Text Search (tsvector)
    for rank, c_id in enumerate(fts_ranked_list, start=1):
        rrf_contrib = 1.0 / (RRF_K + rank)
        rrf_scores[c_id] = rrf_scores.get(c_id, 0.0) + rrf_contrib
        rank_breakdowns.setdefault(c_id, {})['fts_rank'] = rank

    # 3c. Add scores from Keyword & Phrase ILIKE Matching
    for rank, c_id in enumerate(phrase_ranked_list, start=1):
        rrf_contrib = 1.0 / (RRF_K + rank)
        rrf_scores[c_id] = rrf_scores.get(c_id, 0.0) + rrf_contrib
        rank_breakdowns.setdefault(c_id, {})['phrase_rank'] = rank

    for c_id, info in chunk_info_map.items():
        info['score'] = rrf_scores.get(c_id, 0.0)
        info['rank_info'] = rank_breakdowns.get(c_id, {})

    sorted_rrf_candidates = sorted(chunk_info_map.values(), key=lambda x: x['score'], reverse=True)
    _logger.info(
        "[RAG_DEBUG][RRF]\n"
        "  - vector_count: %d\n"
        "  - fts_count: %d\n"
        "  - ilike_count: %d\n"
        "  - merged_unique_count: %d\n"
        "  - top_20: %s",
        len(vector_ranked_list), len(fts_ranked_list), len(phrase_ranked_list),
        len(chunk_info_map),
        json.dumps([
            {
                'chunk_id': ch['id'],
                'document_id': ch['document_id'],
                'parent_id': ch['parent_id'],
                'rrf_score': round(ch['score'], 6),
                'source_ranks': ch.get('rank_info', {}),
                'sequence': ch['sequence'],
                'preview_150_200': ch['content'][:200].replace('\n', ' ')
            }
            for ch in sorted_rrf_candidates[:20]
        ], ensure_ascii=False, indent=2)
    )

    # 4. Bidirectional Neighbor Chunk Expansion (sequence - 1 and sequence + 1)
    top_candidates = sorted(chunk_info_map.values(), key=lambda x: x['score'], reverse=True)[:limit]
    expanded_chunk_keys = set()
    for ch in top_candidates[:5]:
        if ch['sequence'] > 1:
            expanded_chunk_keys.add((ch['document_id'], ch['sequence'] - 1))
        expanded_chunk_keys.add((ch['document_id'], ch['sequence'] + 1))

    if expanded_chunk_keys:
        try:
            or_conditions = " OR ".join(["(c.document_id = %s AND c.sequence = %s)"] * len(expanded_chunk_keys))
            flat_params = []
            for d_id, seq in expanded_chunk_keys:
                flat_params.extend([d_id, seq])
            
            sql_neighbor = f"""
                SELECT c.id, c.content, c.sequence, c.document_id, d.name,
                       c.parent_id, p.content AS parent_content, p.sequence AS parent_sequence
                  FROM topic_chatbot_chunk c
                  JOIN topic_chatbot_document d ON d.id = c.document_id
                  LEFT JOIN topic_chatbot_chunk p ON p.id = c.parent_id
                 WHERE {or_conditions}
            """
            env.cr.execute(sql_neighbor, flat_params)
            for row in env.cr.fetchall():
                c_id, content, sequence, doc_id, doc_name, parent_id, parent_content, parent_seq = row
                if c_id not in chunk_info_map:
                    neighbor_baseline_score = 0.5 * (1.0 / (RRF_K + 15))
                    chunk_info_map[c_id] = {
                        'id': c_id,
                        'content': content,
                        'sequence': sequence or 1,
                        'document_id': doc_id,
                        'document_name': doc_name or 'Unknown Document',
                        'parent_id': parent_id,
                        'parent_content': parent_content,
                        'parent_sequence': parent_seq,
                        'score': neighbor_baseline_score,
                        'rank_info': {'neighbor': True}
                    }
        except Exception as e:
            _logger.debug("Neighbor expansion skipped: %s", str(e))

    _logger.info(
        "[RAG_DEBUG][NEIGHBOR]\n"
        "  - original_top_chunk_ids: %s\n"
        "  - expanded_chunk_keys: %s\n"
        "  - total_after_expansion: %d",
        [ch['id'] for ch in top_candidates[:5]],
        [list(k) for k in expanded_chunk_keys],
        len(chunk_info_map)
    )

    # 5. Small-to-Big Resolution (Map Child hits to Parent Context) & Final Sorting
    parent_context_map = {}
    for ch in sorted(chunk_info_map.values(), key=lambda x: x['score'], reverse=True):
        if ch.get('parent_id') and ch.get('parent_content'):
            # Key on parent chunk ID to deduplicate multiple child matches into the single rich parent block
            p_key = ('parent', ch['document_id'], ch['parent_id'])
            if p_key not in parent_context_map:
                parent_context_map[p_key] = {
                    'id': ch['parent_id'],
                    'content': ch['parent_content'],
                    'sequence': ch.get('parent_sequence') or ch['sequence'],
                    'document_id': ch['document_id'],
                    'document_name': ch.get('document_name', 'Unknown Document'),
                    'score': ch['score'],
                    'rank_info': ch.get('rank_info', {}),
                    'child_ids': [ch['id']],
                    'is_parent': True,
                }
            else:
                # Accumulate score when multiple child chunks hit the same parent
                parent_context_map[p_key]['score'] += ch['score']
                if ch['id'] not in parent_context_map[p_key].get('child_ids', []):
                    parent_context_map[p_key].setdefault('child_ids', []).append(ch['id'])
        else:
            # Standard legacy chunk
            c_key = ('chunk', ch['document_id'], ch['id'])
            if c_key not in parent_context_map:
                item_copy = dict(ch)
                item_copy['child_ids'] = [ch['id']]
                parent_context_map[c_key] = item_copy

    parent_debug_list = []
    for p_key, p_info in sorted(parent_context_map.items(), key=lambda x: x[1]['score'], reverse=True):
        p_content = p_info.get('content') or ''
        has_tao_duyet_gia = ("tạo duyệt giá" in p_content.lower()) or ("3.2.1. tạo duyệt giá" in p_content.lower()) or ("tạo duyệt giá" in p_info.get('document_name', '').lower())
        parent_debug_list.append({
            'parent_id': p_info.get('id'),
            'document_id': p_info.get('document_id'),
            'document_name': p_info.get('document_name'),
            'accumulated_score': round(p_info.get('score', 0.0), 6),
            'child_ids': p_info.get('child_ids', []),
            'contains_target_phrase_tao_duyet_gia': has_tao_duyet_gia,
            'preview_300': p_content[:300].replace('\n', ' ')
        })

    _logger.info(
        "[RAG_DEBUG][PARENT]\n"
        "  - number_of_unique_parents: %d\n"
        "  - parents: %s",
        len(parent_context_map),
        json.dumps(parent_debug_list, ensure_ascii=False, indent=2)
    )

    # Select top distinct context blocks (max 4-5 parent/standard blocks to control prompt tokens)
    max_context_blocks = min(limit, 5)
    final_chunks = sorted(parent_context_map.values(), key=lambda x: x['score'], reverse=True)[:max_context_blocks]
    final_chunks.sort(key=lambda x: (x['document_id'], x['sequence']))

    # Structured log for retrieved chunks: id, similarity/rank score, 50 chars prefix
    chunks_summary = [
        {
            'id': c['id'],
            'score': round(c.get('score', 0.0), 5),
            'preview_50': (c.get('content') or '')[:50].replace('\n', ' ')
        }
        for c in final_chunks
    ]

    _logger.info(
        "[RETRIEVAL_RESULT]\n"
        "  - retrieval_method: %s\n"
        "  - fallback_reason: %s\n"
        "  - query_text: '%s'\n"
        "  - total_retrieved: %d\n"
        "  - chunks: %s",
        retrieval_method,
        fallback_reason if fallback_reason else "None",
        query_text,
        len(final_chunks),
        json.dumps(chunks_summary, ensure_ascii=False)
    )

    # Detailed Observability Log for Debugging
    _logger.info(
        "=== [HYBRID RAG RETRIEVAL (RRF k=60)] ===\n"
        "User Query: '%s'\n"
        "Extracted Keyphrases: %s\n"
        "Meaningful Words: %s\n"
        "Ranked Lists: Vector=%d, FTS=%d, Phrase=%d | Total Retrieved Chunks: %d\n"
        "%s\n"
        "========================================",
        cleaned_msg,
        keyphrases[:6],
        meaningful_words[:6],
        len(vector_ranked_list),
        len(fts_ranked_list),
        len(phrase_ranked_list),
        len(final_chunks),
        "\n".join([
            f"  -> [Chunk {c['id']}] RRF Score: {c['score']:.5f} | Ranks: {c.get('rank_info', {})} | Doc: '{c.get('document_name', 'Unknown Document')}' (Seq {c['sequence']}) | Preview: {c['content'][:100].replace(chr(10), ' ')}..."
            for c in final_chunks[:5]
        ])
    )
    for c in final_chunks:
        c['tier_activated'] = 'Tier 3 (Chunk-Level Hybrid Search)'
        c['tier_reason'] = 'total_topic_chars > 25000 and Tier 2 did not match'
        c['retrieval_method'] = retrieval_method

    return final_chunks


def log_rag_payload(
    env,
    topic_id,
    user_query,
    route_type=None,
    route_reason=None,
    tier_activated=None,
    tier_reason=None,
    retrieval_method=None,
    chunks=None,
    prompt_context=None,
    conversation_id=None,
    extra_data=None,
):
    """Log full RAG retrieval input/output payload into PostgreSQL table 'topic_chatbot_rag_log'.

    Key Audit Features:
    1. Log exact Intent and Route (SEMANTIC_RAG, STRUCTURED_DATA, SCHEMA_METADATA) + route_reason:
       Verifies whether a question was misrouted (e.g. procedural 'cách phê duyệt' routed to STRUCTURED_DATA).
    2. Log exact Tier activated (Tier 1: Whole-Topic, Tier 2: Document-Level, Tier 3: Chunk-Hybrid):
       Verifies whether the retrieval strategy matched topic scale.
    3. Log exact Prompt Context (context_str) sent to Gemini / Ollama:
       Allows instant diagnosis of:
       - 'Wrong document retrieved' (RRF promoted wrong chunks)
       - 'Right document but corrupted/fragmented text' (bad parent/child chunking)
    4. Auto-creates PostgreSQL table 'topic_chatbot_rag_log' if not exists, guaranteeing immediate zero-downtime execution.
    """
    if env is None:
        try:
            from odoo.http import request
            env = request.env
        except Exception:
            return None

    try:
        # 1. Ensure table and indexes exist in PostgreSQL (Self-Healing schema)
        env.cr.execute("""
            CREATE TABLE IF NOT EXISTS topic_chatbot_rag_log (
                id SERIAL PRIMARY KEY,
                create_date TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'UTC'),
                topic_id INTEGER,
                topic_name VARCHAR,
                conversation_id INTEGER,
                user_query TEXT,
                rewritten_query TEXT,
                route_type VARCHAR,
                route_reason TEXT,
                tier_activated VARCHAR,
                tier_reason TEXT,
                retrieval_method VARCHAR,
                retrieved_chunks_count INTEGER,
                retrieved_chunks_summary TEXT,
                prompt_context TEXT,
                full_payload TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_topic_chatbot_rag_log_create_date ON topic_chatbot_rag_log(create_date DESC);
            CREATE INDEX IF NOT EXISTS idx_topic_chatbot_rag_log_topic_id ON topic_chatbot_rag_log(topic_id);
            CREATE INDEX IF NOT EXISTS idx_topic_chatbot_rag_log_conv_id ON topic_chatbot_rag_log(conversation_id);
        """)

        # 2. Extract metadata and infer missing tier/method from chunks if not explicitly passed
        if chunks and not tier_activated:
            for c in chunks:
                if c.get('tier_activated'):
                    tier_activated = c['tier_activated']
                    tier_reason = c.get('tier_reason')
                    retrieval_method = c.get('retrieval_method') or retrieval_method
                    break

        topic_name = ""
        if topic_id:
            try:
                topic_rec = env['topic_chatbot.topic'].browse(int(topic_id))
                if topic_rec.exists():
                    topic_name = topic_rec.name or ""
            except Exception:
                pass

        chunks_summary = []
        if chunks:
            for c in chunks:
                chunks_summary.append({
                    'id': c.get('id'),
                    'document_id': c.get('document_id'),
                    'document_name': c.get('document_name'),
                    'sequence': c.get('sequence'),
                    'score': round(float(c.get('score', 0.0)), 5) if c.get('score') is not None else None,
                    'is_parent': c.get('is_parent', False),
                    'child_ids': c.get('child_ids', []),
                    'preview': (c.get('content') or '')[:200].replace('\n', ' '),
                })

        rewritten_q = ''
        if isinstance(extra_data, dict):
            rewritten_q = extra_data.get('search_query') or extra_data.get('rewritten_query') or ''

        payload_dict = {
            'user_query': user_query,
            'rewritten_query': rewritten_q,
            'route_type': route_type,
            'route_reason': route_reason,
            'tier_activated': tier_activated,
            'tier_reason': tier_reason,
            'retrieval_method': retrieval_method,
            'retrieved_chunks_count': len(chunks) if chunks else 0,
            'chunks_summary': chunks_summary,
            'extra_data': extra_data or {},
        }

        # 3. Insert audit log record
        sql_insert = """
            INSERT INTO topic_chatbot_rag_log (
                topic_id, topic_name, conversation_id,
                user_query, rewritten_query, route_type, route_reason,
                tier_activated, tier_reason, retrieval_method,
                retrieved_chunks_count, retrieved_chunks_summary,
                prompt_context, full_payload
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s
            ) RETURNING id;
        """
        env.cr.execute(sql_insert, (
            int(topic_id) if topic_id else None,
            topic_name,
            int(conversation_id) if conversation_id else None,
            user_query or "",
            rewritten_q,
            route_type or "",
            route_reason or "",
            tier_activated or "",
            tier_reason or "",
            retrieval_method or "",
            len(chunks) if chunks else 0,
            json.dumps(chunks_summary, ensure_ascii=False),
            prompt_context or "",
            json.dumps(payload_dict, ensure_ascii=False)
        ))
        log_id = env.cr.fetchone()[0]
        env.cr.commit()

        _logger.info(
            ">>> [RAG_AUDIT_LOG] Saved RAG Payload Audit ID=%s | Route: %s | Tier: %s | Chunks: %d | Context Length: %d chars",
            log_id, route_type, tier_activated, len(chunks) if chunks else 0, len(prompt_context or "")
        )
        return log_id
    except Exception as e:
        _logger.error("[RAG_AUDIT_LOG_ERROR] Failed to save RAG payload log: %s", str(e))
        return None


