# Decisions Log

## [D001] Extract system prompt thành method riêng
- **Date:** 2026-07-27
- **Context:** System prompt ~200 dòng copy-paste giữa `ask()` và `ask_stream()`.
- **Decision:** Tách thành `_build_system_instruction(self, context_str)`; cả 2 method đều gọi method này.
- **Consequence:** DRY, maintenance cost giảm, sửa prompt chỉ cần 1 nơi.

## [D002] Admin conversation rule → full access
- **Date:** 2026-07-27
- **Context:** Admin rule `[('user_id', '=', user.id)]` giống hệt user rule → admin không audit được conversation người khác.
- **Decision:** Đổi thành `[(1, '=', 1)]` để admin có full access.
- **Consequence:** Admin có thể monitor và debug conversation của mọi user.

## [D003] Xóa `_format_context_chunk()` — dead code
- **Date:** 2026-07-27
- **Context:** Method được định nghĩa nhưng không được gọi ở bất kỳ đâu.
- **Decision:** Xóa hoàn toàn.
- **Consequence:** Giảm code noise.

## [D004] Orphan user message → delete on error
- **Date:** 2026-07-27
- **Context:** Khi API fail sau khi user message đã save, user message bị orphan (không có bot reply).
- **Decision:** Dùng flag `bot_reply_saved` + search-delete orphan trong `finally`.
- **Consequence:** Không còn dữ liệu rác; tránh confsue cho user.

## [D005] GIN index cho Full-Text Search
- **Date:** 2026-07-27
- **Context:** `to_tsvector` trong `_retrieve_context()` chạy sequential scan.
- **Decision:** Tạo `data/fts_index.xml` gọi `_create_fts_index()` trong `chunk.py`, index GIN `to_tsvector('simple', content)`.
- **Consequence:** FTS performance O(log n) thay vì O(n); chỉ chạy 1 lần khi module init.

## [D006] `attachment=True` cho Binary field
- **Date:** 2026-07-27
- **Context:** `datas` field mặc định lưu trong DB → phình database.
- **Decision:** Thêm `attachment=True` để Odoo lưu vào `ir.attachment` (filestore).
- **Consequence:** Giảm áp lực DB; backup dễ hơn.

## [D007] `is_admin` field — NOT stored (intentionally)
- **Date:** 2026-07-27
- **Context:** Đề xuất thêm `store=True` cho `is_admin` compute field.
- **Decision:** **Không thay đổi.** `is_admin` là context-dependent (phụ thuộc current user), không phải thuộc tính của record. Stored sẽ gây sai logic.
- **Consequence:** Giữ nguyên behavior (non-stored compute field).

## [D008] Async Document Processing bằng `ir.cron` nội tại
- **Date:** 2026-07-28
- **Context:** Tách text và chunking file PDF dung lượng lớn đang chạy đồng bộ, gây block luồng request của Odoo (Timeout). `ROADMAP.md` đề xuất dùng Queue Job.
- **Decision:** Thay vì cài thêm OCA `queue_job` (gây phụ thuộc module ngoài), sử dụng cơ chế `ir.cron` (Scheduled Actions) chạy ngầm mỗi 1 phút để quét các file có `state='draft'`.
- **Consequence:** Module vẫn độc lập (không dependency OCA), file nặng được xử lý an toàn không treo UI, bù lại thời gian chờ có thể lên tới 1 phút thay vì real-time.

## [D009] Token-limit management: Character-based thay vì Message-count
- **Date:** 2026-07-29
- **Context:** Hệ thống cũ lấy cố định `limit=20` tin nhắn gần nhất để gửi lên Gemini API. Nếu mỗi tin nhắn dài (ví dụ bot trả lời bảng dữ liệu), 20 tin nhắn có thể vượt quá giới hạn context window → lỗi `MAX_TOKENS`.
- **Decision:** Thay `limit=20` bằng cơ chế tính tổng ký tự (`MAX_CHARS = 30000`, tương đương ~8000 tokens). Quét từ tin nhắn mới nhất ngược lại, khi vượt ngưỡng thì ngừng. Tin nhắn đầu tiên (mới nhất) luôn được giữ ngay cả khi vượt limit để tránh context rỗng.
- **Consequence:** Loại bỏ hoàn toàn lỗi MAX_TOKENS; hội thoại dài vẫn hoạt động ổn định; AI luôn nhớ bối cảnh gần nhất.

## [D010] Rate Limiting dựa trên `topic_chatbot.message` count
- **Date:** 2026-07-30
- **Context:** Không có cơ chế chặn spam → một user có thể gửi hàng chục request/phút, gây tốn quota API Gemini và ảnh hưởng hiệu năng server.
- **Decision:** Tạo method `_check_rate_limit(env, user_id)` đếm số tin nhắn `role='user'` trong 60 giây gần nhất (cross-conversation). Ngưỡng mặc định: 5 tin/phút. Method nhận `env` làm tham số để có thể test được trong TransactionCase (không phụ thuộc `request`).
- **Consequence:** Chặn hiệu quả spam API; ngưỡng có thể điều chỉnh qua class constants; logic per-user nên không ảnh hưởng user khác.

## [D011] Controller Unit Testing & Timezone Synchronization
- **Date:** 2026-07-30
- **Context:** `datetime.now()` gây timezone mismatch với `create_date` trong Postgres (UTC). Đồng thời `unittest.mock.patch('odoo.http.request')` trên Python 3.10 gây lỗi `RuntimeError: object unbound` do Werkzeug LocalProxy.
- **Decision:** Dùng `datetime.utcnow()` tường minh trong `_check_rate_limit`. Đối với unit tests của controller, patch trực tiếp `odoo.addons.topic_chatbot.controllers.main.request` với `new=mock` và `self.env(user=target_uid)` để tránh LocalProxy inspection và áp dụng đúng Odoo 17 Record Rules.
- **Consequence:** Tất cả 105 unit test cases (models, controllers, streaming) chạy thành công 100% không còn lỗi/failure.
