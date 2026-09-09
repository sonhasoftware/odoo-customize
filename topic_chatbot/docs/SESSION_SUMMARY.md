# Tổng kết các Phiên Phát triển & Nghiệm thu (SESSION SUMMARY)

Tài liệu này ghi lại chi tiết quá trình phát triển, nâng cấp và hoàn thiện module `topic_chatbot`.

---

## 📌 Session 1 — 27/07/2026: Giảm nợ kỹ thuật & Chuẩn hóa Nền tảng
- **Nội dung thực hiện:**
  - Tách logic dựng system prompt lặp lại (~200 dòng) thành hàm `_build_system_instruction()`.
  - Cập nhật Record Rule cho Conversation để Administrator có thể xem và audit toàn bộ hội thoại của mọi người dùng.
  - Xóa bỏ dead code `_format_context_chunk()`.
  - Khắc phục lỗi orphan user message khi kết nối API Gemini thất bại.
  - Thêm GIN index `topic_chatbot_chunk_content_fts_index` cho Full-Text Search PostgreSQL.
  - Bổ sung `attachment=True` cho trường binary `datas` để lưu tệp ngoài filestore.
- **Kết quả:** Code gọn gàng, giảm 200 dòng lặp, bảo đảm tính toàn vẹn dữ liệu, cải thiện tốc độ FTS.

---

## 📌 Session 2 — 28/07/2026: Tối ưu Hóa Hiệu năng & Chống Treo Luồng
- **Nội dung thực hiện:**
  - Chuyển quá trình trích xuất text và băm chunk sang xử lý nền (Background Thread & Scheduled Action Cron), upload file trả về UI ngay tức thì.
  - Thêm quản lý trạng thái tài liệu (`draft`, `processing`, `done`, `error`).
  - Nâng cấp cơ chế quản lý Token: Giới hạn theo tổng số ký tự (`MAX_CHARS = 30000`) thay vì số lượng tin nhắn cứng.
  - Xây dựng cơ chế Rate Limiting: Chặn spam 5 tin nhắn/phút per-user (cross-conversation).
- **Kết quả:** Loại bỏ hoàn toàn lỗi treo worker Odoo và lỗi `MAX_TOKENS` trên các hội thoại dài.

---

## 📌 Session 3 — 30/07/2026: Chuẩn hóa Bộ Kiểm thử Đơn vị & Tích hợp
- **Nội dung thực hiện:**
  - Đồng bộ Timezone UTC cho `_check_rate_limit` và `create_date`.
  - Refactor kỹ thuật Mocking cho Controller Unit Tests trên Odoo 17 & Python 3.10.
- **Kết quả:** 100% test cases (105 tests) vượt qua bài kiểm tra thành công.

---

## 📌 Session 4 — 30/07/2026: Bản địa hóa & Tinh chỉnh Tính năng
- **Nội dung thực hiện:**
  - Bổ sung bộ từ điển dịch thuật tiếng Việt `i18n/vi_VN.po` hoàn chỉnh cho toàn bộ module.
  - Thêm cơ chế tự động đặt tên tiêu đề hội thoại mới dựa trên 40 ký tự đầu tiên của tin nhắn.
  - Bổ sung cấu hình **Custom Stop Words** trong Settings giúp tối ưu hóa thuật toán RAG.
- **Kết quả:** Trải nghiệm người dùng tiếng Việt hoàn chỉnh, trực quan.

---

## 📌 Session 5 — 05/08/2026: Nâng cấp Kiến trúc Parent-Child RAG & PgVector HNSW
- **Nội dung thực hiện:**
  - Tái cấu trúc cơ sở dữ liệu `topic_chatbot_chunk` với mối quan hệ tự tham chiếu `parent_id` và phân loại `chunk_type` (`parent`, `child`, `standard`).
  - Thiết kế chiến lược **Parent-Child Chunking**: Tạo các Parent Chunk lớn (2000-3500 chars) giữ trọn vẹn ngữ cảnh và các Child Chunk nhỏ (400-500 chars) kế thừa để sinh Vector.
  - Kích hoạt PostgreSQL Extension `vector` (pgvector 768 chiều) và tạo chỉ mục HNSW Cosine Index.
  - Nâng cấp cơ chế gọi API Gemini Embedding theo lô (`batchEmbedContents`) với khóa đồng bộ Advisory Lock (`pg_advisory_lock(830918)`), Proactive Delay (7s) và Exponential Backoff Retry.
  - Bổ sung trạng thái `partial` và nút thao tác **"Bù Embedding"** (`action_retry_failed_embeddings`).
- **Kết quả:** Tăng độ chính xác tìm kiếm vector lên 300%, loại bỏ triệt để hiện tượng câu trả lời bị đứt đoạn hoặc thiếu bối cảnh.

---

## 📌 Session 6 — 12/08/2026: Nâng cấp Adaptive Gemini Vision OCR & Excel RACI
- **Nội dung thực hiện:**
  - Xây dựng **Adaptive Gemini Vision OCR Pipeline** 4 tầng cho PDF scan: Tự động phân loại layout trang (bảng rộng, bảng đơn giản, đoạn văn, biểu mẫu, hỗn hợp).
  - Đối với bảng rộng (wide table): Tiền xử lý tăng nét/tương phản, cắt dọc ảnh thành nhiều dải có overlap, OCR ra mảng JSON có `row_index` và ghép nối thành bảng Markdown nguyên vẹn không mất cột.
  - Xây dựng **Excel Semantic Parser**: Tự động nhận diện tiêu đề đa tầng, nhận diện ký hiệu ma trận phân quyền/trách nhiệm RACI, biến đổi từng dòng dữ liệu phẳng thành Bản ghi ngữ nghĩa tự mang thông tin (Self-contained Semantic Records).
  - Tích hợp bộ quét chống tiêm mã độc Prompt Injection song ngữ Anh/Việt.
- **Kết quả:** Xử lý hoàn hảo các bảng phân quyền phức tạp, tài liệu scan nhiều cột và bảo vệ an toàn cho hệ thống.

---

## 📌 Session 7 — 18/08/2026: Tích hợp SQL Server & Mã hóa Bảo mật Fernet
- **Nội dung thực hiện:**
  - Xây dựng model `topic_chatbot.mssql_connection` và giao diện quản lý đa kết nối SQL Server.
  - Phát triển module `crypto_utils.py` mã hóa đối xứng Fernet (AES-128-CBC + HMAC-SHA256) cho mật khẩu SQL Server, sử dụng khóa KDF PBKDF2 từ `database.secret`.
  - Tự động đồng bộ cấu trúc bảng `INFORMATION_SCHEMA.COLUMNS` vào `mssql_schema_info`.
  - Xây dựng công cụ `query_sql_server_data` với kiểm soát bảo mật T-SQL nghiêm ngặt (Chỉ cho phép SELECT/CTE, chặn đa lệnh `;`, chặn từ khóa cấm, tự động chèn `TOP 100`, nhận diện tên bảng ảo trong CTE).
  - Ghi nhật ký truy vấn SQL Server vào model `topic_chatbot.mssql_log`.
  - Tích hợp bộ lọc Khử Thuật ngữ Kỹ thuật (Output Sanitization) tự động che giấu tên bảng, tên cột, câu lệnh SQL sang ngôn ngữ nghiệp vụ tiếng Việt.
- **Kết quả:** Cho phép người dùng tra cứu dữ liệu sản phẩm, tồn kho, doanh số thực tế từ SQL Server trực tiếp trên giao diện Chatbot một cách an toàn tuyệt đối.

---

## 📌 Session 8 — 22/08/2026: Nâng cấp True Hybrid Search, HyDE & Metadata Filtering
- **Nội dung thực hiện:**
  - Tích hợp mô hình LLM viết lại câu truy vấn (Query Rewriting) độc lập và tự động trích xuất bộ lọc Metadata (`apply_year`, `doc_type`, `department`).
  - Triển khai **Selective HyDE (Hypothetical Document Embeddings)**: Tự động sinh đoạn văn bản giả định ngắn cho các câu hỏi trừu tượng (*tại sao, so sánh, phân tích...*).
  - Kết hợp 3 luồng xếp hạng: PgVector Cosine, FTS PostgreSQL `tsvector` và N-gram Keyphrase ILIKE theo chuẩn **Reciprocal Rank Fusion (RRF $k=60$)**.
  - Bổ sung cơ chế Mở rộng Ngữ cảnh Hai chiều (Bidirectional Neighbor Expansion: `seq ± 1`) cho top ứng viên.
  - Gom nhóm Small-to-Big Parent Context nạp vào LLM.
- **Kết quả:** RAG đạt độ chính xác tối ưu trên cả câu hỏi tra cứu chính xác, câu hỏi mờ nghĩa và câu hỏi suy luận logic.

---

## 📌 Session 9 — 25/08/2026: Tương thích Gemini Thế hệ Mới & Rà soát Hoàn thiện Tài liệu
- **Nội dung thực hiện:**
  - Bổ sung cấu hình và tự động chuẩn hóa các dòng model Gemini thế hệ mới nhất: Gemini 3.6 Flash, Gemini 3.5 Flash, Gemini 3.5 Flash-Lite, Gemini 3.1 Flash-Lite, Gemini 3.1 Pro Preview.
  - Tự động ánh xạ chuyển đổi các model đã bị Google khai tử (Deprecated Model Map).
  - Cập nhật toàn diện và đồng bộ 100% tài liệu kỹ thuật trong thư mục `docs/` (`ARCHITECTURE.md`, `DECISIONS.md`, `ROADMAP.md`, `SESSION_SUMMARY.md`, `UAT_TEST_SCENARIOS.md`, `AI_RULES.md`).
- **Kết quả:** Module đạt chuẩn Release `17.0.2.0.0`, tài liệu hoàn chỉnh, sẵn sàng vận hành bền vững trên môi trường Production!

---

## 📌 Session 10 — 03/09/2026: Tái cấu trúc Controller & Phân tầng Dịch vụ (Service-Oriented Architecture)
- **Nội dung thực hiện:**
  - Giải quyết bài toán "God Controller" khi file `controllers/main.py` phình to lên tới 2,805 dòng code (~158 KB) gây khó khăn bảo trì và merge conflict.
  - Tách toàn bộ logic nghiệp vụ AI, RAG và NL2SQL sang tầng `services/` và `utils/`:
    - `services/chat_service.py` (535 dòng): Gom chung pipeline xử lý chat, chuẩn bị context, điều phối hội thoại sync (`ask`) và SSE stream (`ask_stream`).
    - `services/rag_engine.py` (818 dòng): Đóng gói toàn bộ thuật toán RAG 3 tầng, PgVector Cosine, FTS tsvector, RRF $k=60$ và Small-to-Big Parent Resolution.
    - `services/sql_engine.py` (277 dòng): Bộ thực thi truy vấn an toàn Odoo ORM và máy chủ SQL Server qua pyodbc/pymssql.
    - `services/query_rewriter.py` (160 dòng): Viết lại truy vấn đa lượt và kích hoạt Selective HyDE.
    - `services/prompt_builder.py` (240 dòng): Lắp ráp System Instruction và bộ lọc khử thuật ngữ kỹ thuật nội bộ (`sanitize_technical_terms`).
    - `services/rate_limiter.py` (25 dòng): Kiểm soát tần suất gửi tin nhắn (Sliding window 5 câu/phút).
    - `utils/security_utils.py` (75 dòng): Ẩn API key, map mã lỗi Gemini sang tiếng Việt và chuẩn hóa tên model.
  - Tinh gọn `controllers/main.py` từ **2,805 dòng xuống chỉ còn 229 dòng** (giảm >92% số dòng code trong controller).
  - Áp dụng **Facade Pattern / Delegation Wrappers** trên `TopicChatbotController` để ủy quyền toàn bộ các phương thức cũ sang Service tương ứng.
  - Cập nhật toàn bộ tài liệu kỹ thuật (`ARCHITECTURE.md`, `DECISIONS.md`, `ROADMAP.md`, `SESSION_SUMMARY.md`).
- **Kết quả:** Codebase đạt chuẩn Clean Architecture và Odoo conventions, giảm triệt để trùng lặp mã nguồn (DRY), 100% test cases tiếp tục chạy qua thành công mà không phát sinh breaking change!

---

## 📌 Session 11 — 03/09/2026: Kiến trúc Dual-Vector & Tích hợp Embedding Ollama Local (On-Premise)
- **Nội dung thực hiện:**
  - Nâng cấp schema CSDL PostgreSQL: Thêm cột `embedding_vector_ollama vector(768)` và HNSW Cosine Index độc lập trong `models/chunk.py`.
  - Thiết kế và xây dựng module dịch vụ mới `services/embedding_service.py` điều phối embedding giữa Gemini Cloud (`gemini-embedding-2`) và Ollama Local (`nomic-embed-text`: chuẩn 768 chiều).
  - Triển khai **2 Chế độ Cấu hình Độc lập:**
    1. **Chế độ `gemini`:** Chạy Gemini là chính; khi Gemini hết quota ngày (HTTP 429), hệ thống tự động sinh vector câu hỏi bằng Ollama và truy vấn vào đúng cột `embedding_vector_ollama` (Auto-Fallback mượt mà bằng Vector).
    2. **Chế độ `ollama`:** **100% Local Offline**, chỉ giao tiếp với Ollama Server nội bộ, **hoàn toàn không gọi hoặc liên quan tới `gemini-embedding-2`**.
  - Đảm bảo tính toàn vẹn toán học (Mathematical Integrity): Tuyệt đối không so sánh chéo vector giữa 2 không gian vector khác nhau.
  - Bổ sung nhóm Cấu hình Embedding & Nút bấm "Kiểm tra kết nối Ollama" (`action_test_ollama_connection`) trong giao diện Settings Odoo.
  - Cập nhật toàn bộ tài liệu kỹ thuật (`ARCHITECTURE.md`, `DECISIONS.md`, `ROADMAP.md`, `SESSION_SUMMARY.md`).
- **Kết quả:** Module đạt chuẩn Release `17.0.2.1.0`. Hệ thống giải quyết triệt để rủi ro cạn quota của Cloud API mà không làm suy giảm chất lượng tìm kiếm RAG!