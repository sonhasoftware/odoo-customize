# AI_RULES.md — Nguyên tắc Kỹ thuật & Chuẩn mực Phát triển Module Topic Chatbot

Tài liệu này định nghĩa các quy chuẩn kiến trúc, chất lượng mã nguồn, kiểm thử và tài liệu hóa bắt buộc phải tuân thủ trong quá trình phát triển module `topic_chatbot`.

---

## 1. Chuẩn mực Chất lượng Mã nguồn (Code Quality)
1. **Bảo mật là trên hết (Security First):**
   - Tuyệt đối không lưu mật khẩu hoặc token dưới dạng plaintext. Luôn sử dụng mã hóa đối xứng Fernet qua `crypto_utils.py` cho các tham số nhạy cảm.
   - Tuyệt đối không log API key hoặc để lộ traceback chứa chuỗi kết nối ra ngoài giao diện người dùng.
   - Bắt buộc kiểm tra quyền truy cập (ACL & Record Rules) trước khi xử lý dữ liệu.
2. **Khử Thuật ngữ Kỹ thuật (Output Sanitization):**
   - Phản hồi của AI ra giao diện người dùng phải được chuyển hóa thành ngôn ngữ nghiệp vụ tiếng Việt; không để lộ tên bảng SQL, mã cột, tên model Odoo hay câu lệnh truy vấn.
3. **DRY (Don''t Repeat Yourself):**
   - Bất kỳ đoạn mã nào lặp lại trên 3 dòng phải được đóng gói thành phương thức hoặc hằng số dùng chung.
4. **Không để Dead Code:**
   - Xóa bỏ ngay các phương thức, biến hoặc route không còn được sử dụng.

---

## 2. Kiến trúc & Hiệu năng (Architecture & Performance)
5. **Xử lý tác vụ nặng qua Background Thread & Cron:**
   - Các tác vụ phân tích tệp tin nặng (PDF scan, OCR, băm chunk, sinh embeddings) phải chạy trong daemon background thread hoặc scheduled action cron, tuyệt đối không block luồng Web HTTP của Odoo.
6. **Đồng bộ Quota bằng PostgreSQL Advisory Lock:**
   - Sử dụng `pg_advisory_lock` / `pg_try_advisory_lock` với key số nguyên quy định (`830917` cho xử lý file, `830918` cho sinh embeddings) để tránh race conditions giữa các Odoo worker.
7. **Parent-Child Chunking Strategy:**
   - Luôn duy trì chiến lược Parent-Child: Sinh vector trên Child Chunk (400-500 chars) và nạp ngữ cảnh vào LLM qua Parent Chunk (2000-3500 chars).
8. **Mô hình Hybrid Search RRF ($k=60$):**
   - Kết hợp 3 luồng tìm kiếm: PgVector Cosine, FTS `tsvector` và N-gram Keyphrase ILIKE; luôn mở rộng ngữ cảnh lân cận (`seq ± 1`).
9. **Field ngữ cảnh không được Stored:**
   - Các trường phụ thuộc ngữ cảnh người dùng hiện tại (như `is_admin`) phải là non-stored computed field.
10. **Tuân thủ Thin Controller & Service Layer Pattern:**
   - Controller chỉ đóng vai trò là HTTP Gateway mỏng (nhận request, check auth, gọi service, trả response/SSE).
   - Toàn bộ logic nghiệp vụ AI, RAG, Text-to-SQL và Prompt Builder bắt buộc phải nằm trong thư mục `services/` hoặc `utils/` tương ứng, không viết logic nghiệp vụ phức tạp trực tiếp trong controller.

---

## 3. Quy chuẩn Kiểm thử & Tài liệu hóa (Testing & Documentation)
10. **Kiểm thử Đơn vị & Tích hợp (Test Coverage):**
    - Mọi Model phải có unit tests kiểm tra CRUD, constraints và logic nghiệp vụ.
    - Mọi Controller endpoint phải có integration tests kiểm tra xác thực, phân quyền, xử lý lỗi và luồng streaming SSE.
11. **Tính Đồng bộ của Thư mục Tài liệu (`docs/`):**
    - Mọi nâng cấp tính năng mới phải được cập nhật đồng thời vào 6 tài liệu trong `docs/`:
      - `ARCHITECTURE.md`: Thiết kế kiến trúc kỹ thuật chi tiết.
      - `DECISIONS.md`: Ghi lại Architecture Decision Records (ADRs) với nguyên nhân và hệ quả.
      - `ROADMAP.md`: Theo dõi tiến độ và định hướng tương lai.
      - `SESSION_SUMMARY.md`: Tổng kết công việc đã thực hiện theo từng phiên.
      - `UAT_TEST_SCENARIOS.md`: Kịch bản kiểm thử chấp nhận người dùng.
      - `AI_RULES.md`: Bộ quy tắc phát triển.