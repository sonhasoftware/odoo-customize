# Session 1 — 27/07/2026

## Mục tiêu
Giảm nợ kỹ thuật, fix critical bugs, chuẩn bị cho production.

## Công việc đã thực hiện

| # | Task | File | Trạng thái |
|---|------|------|------------|
| 1 | Extract system prompt trùng (~200 dòng) → `_build_system_instruction()` | `controllers/main.py` | Done |
| 2 | Fix admin record rule cho conversation | `security/security.xml` | Done |
| 3 | Xóa dead code `_format_context_chunk()` | `controllers/main.py` | Done |
| 4 | Fix orphan user message khi API fail | `controllers/main.py` | Done |
| 5 | Add GIN index cho FTS | `models/chunk.py`, `data/fts_index.xml` | Done |
| 6 | Add `attachment=True` cho `datas` field | `models/document.py` | Done |

## Kết quả
- Giảm ~200 dòng code trùng lặp
- Admin có thể xem tất cả conversation (trước đây chỉ xem được của mình)
- Không còn orphan user message khi Gemini API fail
- Bug fix: `bot_reply_saved = True` khi không có API key (tránh xóa user message nhầm)
- FTS performance được cải thiện với GIN index
- File documents lưu vào filestore thay vì database
- 15 test cases cho Session 1 (models + rules + index + attachment + cleanup logic)

## Remaining (Session 2+)
- Async document processing (queue job)
- Token-limit management cho chat history
- Rate limiting
- Unit tests
- i18n/translations

---

# Session 2 — 28/07/2026

## Mục tiêu
Production hardening: Tối ưu hóa hiệu năng và bảo vệ tài nguyên hệ thống (Tránh treo luồng).

## Công việc đã thực hiện

| # | Task | File | Trạng thái |
|---|------|------|------------|
| 1 | Async document processing (queue job) | `models/document.py`, `data/cron.xml`, `views/topic_views.xml` | Done |
| 2 | Token-limit management for chat history | `controllers/main.py` | Done |
| 3 | Rate limiting / abuse prevention | `controllers/main.py` | Done |
| 4 | Unit tests for Session 2 | `tests/test_session2.py` | Done |

## Kết quả
- Quá trình upload file trả về kết quả UI ngay lập tức (<0.1s).
- File lớn được băm nhỏ ở background process (thông qua `ir.cron` mỗi 1 phút).
- Thêm trường `state` vào Document (Draft, Processing, Done, Error) để theo dõi tiến độ.
- Hệ thống module vẫn giữ tính độc lập, không phụ thuộc OCA.
- Token-limit: Thay `limit=20` tin nhắn bằng giới hạn ký tự (`MAX_CHARS = 30000`) → loại bỏ lỗi MAX_TOKENS khi hội thoại dài.
- Rate limiting: Chặn spam 5 tin nhắn/phút per-user, cross-conversation.
- Hoàn thành 8 test cases trong `test_session2.py` (3 Async + 2 Token-limit + 3 Rate-limit).

## Session 2 — COMPLETED ✅
