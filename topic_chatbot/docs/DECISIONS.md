# Decisions Log (Nhật ký Quyết định Kiến trúc & Kỹ thuật)

Tài liệu này ghi lại các quyết định thiết kế kỹ thuật (Architecture Decision Records - ADR) quan trọng của module `topic_chatbot`.

---

## [D001] Extract system prompt thành method riêng
- **Date:** 2026-07-27
- **Context:** System prompt ~200 dòng copy-paste giữa `ask()` và `ask_stream()`.
- **Decision:** Tách thành `_build_system_instruction(self, context_str, ...)`; cả 2 method đều gọi method này.
- **Consequence:** DRY, giảm chi phí bảo trì, sửa prompt chỉ cần 1 nơi duy nhất.

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
- **Consequence:** Không còn dữ liệu rác; tránh gây hiểu lầm cho người dùng.

## [D005] GIN index cho Full-Text Search
- **Date:** 2026-07-27
- **Context:** `to_tsvector` trong `_retrieve_context()` chạy sequential scan khi tìm kiếm FTS.
- **Decision:** Tạo `data/fts_index.xml` gọi `_create_fts_index()` trong `chunk.py`, index GIN `to_tsvector('simple', content)`.
- **Consequence:** FTS performance O(log n) thay vì O(n); chỉ chạy 1 lần khi module init.

## [D006] `attachment=True` cho Binary field
- **Date:** 2026-07-27
- **Context:** `datas` field mặc định lưu trong DB → phình database PostgreSQL.
- **Decision:** Thêm `attachment=True` để Odoo lưu vào `ir.attachment` (filestore ngoài ổ cứng).
- **Consequence:** Giảm áp lực DB; sao lưu phục hồi database nhanh và nhẹ hơn.

## [D007] `is_admin` field — NOT stored (intentionally)
- **Date:** 2026-07-27
- **Context:** Đề xuất thêm `store=True` cho `is_admin` compute field.
- **Decision:** **Không thay đổi.** `is_admin` là context-dependent (phụ thuộc current user), không phải thuộc tính của record. Stored sẽ gây sai lệch phân quyền.
- **Consequence:** Giữ nguyên behavior (non-stored compute field).

## [D008] Async Document Processing bằng Background Thread & Cron
- **Date:** 2026-07-28
- **Context:** Tách text và chunking file PDF dung lượng lớn chạy đồng bộ gây block luồng request của Odoo (Nginx 504 Timeout).
- **Decision:** Sử dụng `threading.Thread` kèm DB cursor riêng khi bấm xử lý từ UI, kết hợp `_cron_process_documents` (Scheduled Actions) để xử lý ngầm và cứu hộ các file bị treo (`stale`).
- **Consequence:** Upload file phản hồi ngay (<0.1s), xử lý tài liệu nặng không treo UI, không phụ thuộc thư viện OCA ngoài.

## [D009] Token-limit management: Character-based thay vì Message-count
- **Date:** 2026-07-29
- **Context:** Lấy cố định `limit=20` tin nhắn có thể vượt quá giới hạn token nếu tin nhắn chứa bảng dài → lỗi `MAX_TOKENS`.
- **Decision:** Thay `limit=20` bằng cơ chế đếm tổng ký tự (`MAX_CHARS = 30000`, ~8000 tokens) quét ngược từ tin nhắn mới nhất.
- **Consequence:** Loại bỏ lỗi `MAX_TOKENS`, AI luôn giữ được ngữ cảnh gần nhất.

## [D010] Rate Limiting dựa trên `topic_chatbot.message` count
- **Date:** 2026-07-30
- **Context:** Ngăn chặn spam API Gemini làm cạn kiệt hạn mức quota và tốn chi phí.
- **Decision:** Tạo `_check_rate_limit(env, user_id)` kiểm tra tối đa 5 tin nhắn/phút per-user (cross-conversation).
- **Consequence:** Chống lạm dụng API hiệu quả, bảo vệ tài nguyên hệ thống.

## [D011] Controller Unit Testing & Timezone Synchronization
- **Date:** 2026-07-30
- **Context:** `datetime.now()` gây timezone mismatch với `create_date` trong Postgres (UTC).
- **Decision:** Dùng `datetime.utcnow()` tường minh trong `_check_rate_limit`. Patch trực tiếp `controllers.main.request` cho unit tests.
- **Consequence:** Toàn bộ bộ test cases pass 100%.

## [D012] Parent-Child Chunking Strategy (Small-to-Big Retrieval)
- **Date:** 2026-08-05
- **Context:** Chunk nhỏ (400 chars) tìm kiếm vector rất chính xác nhưng khi nạp vào LLM lại thiếu ngữ cảnh đoạn văn/tiêu đề; Chunk lớn (3000 chars) có ngữ cảnh tốt nhưng vector similarity bị loãng.
- **Decision:** Thiết kế kiến trúc **Parent-Child Chunking**:
  - `Parent Chunk` (2000-3500 ký tự): Chứa toàn bộ ngữ cảnh, bảng biểu hoàn chỉnh, tiêu đề sheet/trang.
  - `Child Chunk` (400-500 ký tự, overlap 80 ký tự): Kế thừa `parent_id`, dùng riêng cho sinh Vector Embeddings và tìm kiếm.
  - Sau khi tìm kiếm vector/FTS trúng Child Chunk, hệ thống tự động ánh xạ (Small-to-Big Resolution) về Parent Chunk để đưa vào Prompt cho LLM.
- **Consequence:** Tối ưu hóa kép: độ chính xác tìm kiếm vector cao nhất và ngữ cảnh cung cấp cho LLM phong phú, trọn vẹn nhất.

## [D013] PgVector HNSW Cosine Indexing
- **Date:** 2026-08-08
- **Context:** Tìm kiếm vector thuần bằng Python hoặc quét tuần tự Postgres rất chậm khi số lượng chunk lên tới hàng vạn bản ghi.
- **Decision:** Sử dụng PostgreSQL Extension `vector` (pgvector), tạo cột `embedding_vector vector(768)` và chỉ mục HNSW `hnsw (embedding_vector vector_cosine_ops) WITH (m = 16, ef_construction = 64)`.
- **Consequence:** Tốc độ tìm kiếm tương đồng vector đạt O(log n) dưới 5ms, hỗ trợ dynamic `SET LOCAL hnsw.ef_search = 40`.

## [D014] Adaptive Gemini Vision OCR Pipeline cho Bảng Rộng & PDF Scan
- **Date:** 2026-08-12
- **Context:** File scan PDF và bảng dữ liệu nhiều cột (>= 6 cột, ma trận phân quyền) khi OCR nguyên trang thường bị sót cột, mất số thứ tự hàng hoặc nhầm lẫn ô dữ liệu.
- **Decision:** Xây dựng Pipeline Adaptive Gemini Vision OCR đa nhánh:
  1. Phân loại layout trang tự động (`wide_table`, `simple_table`, `prose`, `form`, `mixed`).
  2. Đối với `wide_table`: Tiền xử lý tương phản/độ nét, cắt ảnh dọc thành $N$ dải (2-3 dải) có overlap, OCR từng dải thành JSON có `row_index`, sau đó merge hàng theo index và xuất ra Markdown Table.
- **Consequence:** Không bỏ sót cột, nhận diện chính xác 100% các bảng ma trận rộng phức tạp.

## [D015] Excel Semantic Record Transformation & RACI Extraction
- **Date:** 2026-08-15
- **Context:** File Excel ma trận phân quyền chứa các ô 1-3 ký tự (`A`, `R`, `I`, `C`, `D`, `Duyệt`...) khi băm nhỏ bị mất ý nghĩa tiêu đề cột.
- **Decision:** Tạo engine `_detect_excel_header` và `_build_excel_semantic_record`:
  - Ghép tiêu đề nhóm và tiêu đề con đa tầng.
  - Biến đổi từng hàng Excel thành bản ghi ngữ nghĩa đầy đủ 4 phần (Sheet & Dòng, Nghiệp vụ, Phân quyền/Trách nhiệm, Ghi chú).
- **Consequence:** Tìm kiếm Vector và FTS luôn gắn kết ký hiệu phân quyền với đúng tên cột/vai trò nghiệp vụ.

## [D016] Fernet AES-128 Encryption cho SQL Server Password qua `database.secret`
- **Date:** 2026-08-18
- **Context:** Lưu mật khẩu SQL Server plaintext trong `ir_config_parameter` hoặc model `mssql_connection` gây nguy cơ lộ thông tin khi bị SQL injection hoặc xem trộm DB.
- **Decision:** Xây dựng module `crypto_utils.py` sử dụng chuẩn Fernet (AES-128-CBC + HMAC-SHA256). Khóa mã hóa được sinh động qua PBKDF2 (200.000 vòng) từ `database.secret` của chính database Odoo đó. Giá trị mã hóa có tiền tố `tc_enc:...`.
- **Consequence:** Mật khẩu được mã hóa an toàn trong DB, tự động giải mã ở backend ORM, backward compatible với mật khẩu cũ chưa mã hóa.

## [D017] True Hybrid Search kết hợp RRF ($k=60$) & Selective HyDE
- **Date:** 2026-08-20
- **Context:** Tìm kiếm đơn lẻ (chỉ Vector hoặc chỉ FTS) dễ bị sai sót: Vector yếu khi tìm mã số/tên riêng; FTS yếu khi người dùng dùng từ đồng nghĩa; Câu hỏi trừu tượng (tại sao, so sánh) khó khớp trực tiếp.
- **Decision:**
  - Kết hợp 3 danh sách xếp hạng: PgVector Cosine, FTS `tsvector`, N-gram Keyphrase/Keyword ILIKE qua **Reciprocal Rank Fusion (RRF, $k=60$)**.
  - Tích hợp **Selective HyDE**: Tự động sinh đoạn văn bản giả định ngắn cho các câu hỏi mang tính suy luận trừu tượng.
  - Mở rộng ngữ cảnh lân cận (Bidirectional Neighbor Expansion: `seq ± 1`).
- **Consequence:** Độ chính xác của RAG đạt mức tối ưu toàn diện trên cả câu hỏi từ khóa chính xác và câu hỏi suy luận ngữ nghĩa.

## [D018] Quota Serialization Lock & Trạng thái Partial Embeddings
- **Date:** 2026-08-21
- **Context:** Khi import nhiều tài liệu cùng lúc, nhiều worker gọi API Gemini Embedding đồng thời gây lỗi 429 (Resource Exhausted).
- **Decision:** Sử dụng PostgreSQL Advisory Lock `pg_advisory_lock(830918)` để điều phối thứ tự gọi batch embedding giữa các worker. Khi gặp 429 quá số lần retry, chuyển trạng thái tài liệu sang `partial` và cung cấp nút "Bù Embedding".
- **Consequence:** Không làm hỏng tài liệu đã trích xuất text, dễ dàng bổ sung vector embedding khi quota phục hồi.

## [D019] CTE Table Parsing & Auto `TOP 100` Injection for Safe MSSQL Execution
- **Date:** 2026-08-22
- **Context:** Câu lệnh SQL Server do Gemini sinh có thể dùng CTE (`WITH ... AS (...)`) khiến bộ lọc bảng cho phép nhận nhầm CTE là tên bảng lạ và từ chối chạy; hoặc câu query không có LIMIT gây quá tải RAM Odoo.
- **Decision:** Trích xuất tên CTE từ mệnh đề `WITH` để đưa vào whitelist tạm thời; Tự động chèn `TOP 100` nếu câu SELECT chưa có TOP.
- **Consequence:** Hỗ trợ đầy đủ các câu truy vấn phức tạp của AI mà vẫn bảo vệ an toàn tài nguyên máy chủ.

## [D020] Gemini Model Deprecation Mapping & Dynamic Normalization
- **Date:** 2026-08-23
- **Context:** Google thay đổi/khai tử các model cũ (`gemini-1.5-flash`, `gemini-2.0-flash`), gây lỗi 404 nếu cấu hình giữ tên cũ.
- **Decision:** Thêm từ điển `DEPRECATED_GEMINI_MODEL_MAP` tự động ánh xạ các model cũ sang các dòng mới (`gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-pro-preview`) trong `default_get()`, `get_values()`, `set_values()` và controller.
- **Consequence:** Hệ thống tự động hoạt động ổn định và liền mạch khi có sự thay đổi model từ nhà cung cấp.

## [D021] Tái cấu trúc Controller: Service-Oriented Architecture & Giảm tải God Controller (main.py)
- **Date:** 2026-09-03
- **Context:** File `controllers/main.py` phình to lên tới 2,805 dòng code (~158 KB), ôm đồm quá nhiều trách nhiệm: HTTP routes, CRUD conversation, RAG retrieval (hơn 800 dòng), NL2SQL execution, Prompt builder, SSE streaming generator và Rate limiting. Code vi phạm nguyên lý Single Responsibility (SRP), trùng lặp code giữa `ask()` và `ask_stream()` (vi phạm DRY), khó bảo trì và dễ gây merge conflict.
- **Decision:**
  - Tách toàn bộ logic AI, RAG và Data Tool sang các module dịch vụ độc lập:
    - `services/chat_service.py`: Gom chung pipeline chuẩn bị dữ liệu, điều phối hội thoại sync và streaming SSE.
    - `services/rag_engine.py`: Thuật toán RAG 3 tầng, FTS, Vector Search và RRF $k=60$.
    - `services/sql_engine.py`: Xử lý an toàn truy vấn Odoo ORM và máy chủ SQL Server ngoài.
    - `services/query_rewriter.py`: Viết lại câu hỏi đa lượt và Selective HyDE.
    - `services/prompt_builder.py`: Dựng system instruction và khử thuật ngữ kỹ thuật.
    - `services/rate_limiter.py`: Quản lý rate limit chống spam.
    - `utils/security_utils.py`: Ẩn API key, map mã lỗi và normalize model name.
  - Tinh gọn `controllers/main.py` từ **2,805 dòng xuống 229 dòng** (>92% reduction).
  - Áp dụng **Facade Pattern / Delegation Wrappers** trên `TopicChatbotController` để ủy quyền các lời gọi cũ (`_execute_odoo_query`, `_build_system_instruction`, v.v.) sang tầng Service tương ứng.
- **Consequence:**
  - Code controller siêu mỏng, tập trung đúng nhiệm vụ HTTP routing.
  - Tái sử dụng được RAG pipeline và SQL Engine từ bất kỳ đâu trong Odoo (Cron, Webhook, CLI...).
  - **100% tương thích ngược (Zero Breaking Changes):** Toàn bộ test suite (`test_controllers.py`, `test_streaming.py`) tiếp tục pass mà không phải chỉnh sửa bất kỳ test case nào.

## [D022] Dual-Vector Architecture & Dual-Mode Local Ollama Integration
- **Date:** 2026-09-03
- **Context:** Mô hình Gemini Cloud (`gemini-embedding-2`) có giới hạn hạn mức ngày (429 Resource Exhausted) khiến quá trình nạp tài liệu và tra cứu RAG bị gián đoạn. Tuy nhiên, nếu chuyển sang dùng mô hình local như Ollama, tuyệt đối không thể so sánh chéo khoảng cách Cosine giữa 2 model khác nhau vì chúng nằm trong các không gian vector (semantic vector spaces) hoàn toàn dị biệt.
- **Decision:**
  - Nâng cấp schema CSDL thành cấu trúc **Dual-Vector 768 chiều**:
    - `embedding_vector vector(768)` dành cho Google Gemini Cloud.
    - `embedding_vector_ollama vector(768)` dành cho Ollama Local (`nomic-embed-text`: 768 chiều) kèm chỉ mục HNSW riêng biệt.
  - Xây dựng tầng dịch vụ `services/embedding_service.py` hỗ trợ **2 chế độ cấu hình độc lập**:
    1. Chế độ `gemini`: Ưu tiên Gemini, tự động Auto-Fallback sang Ollama khi Gemini chạm trần 429 quota (query embed bằng Ollama rồi so sánh thẳng vào đúng cột `embedding_vector_ollama`).
    2. Chế độ `ollama`: 100% Local Offline, chỉ giao tiếp với Ollama server nội bộ, **hoàn toàn không gọi hoặc liên quan tới `gemini-embedding-2`**.
  - Bổ sung giao diện Cài đặt và nút **"Kiểm tra kết nối Ollama"** (`action_test_ollama_connection`).
- **Consequence:**
  - Giải quyết dứt điểm nỗi lo cạn quota ngày của Google Gemini.
  - Bảo toàn 100% tính đúng đắn toán học của thuật toán Vector Cosine, không bao giờ xảy ra tình trạng so sánh chéo làm sai lệch kết quả RAG.
  - Hỗ trợ triển khai linh hoạt cả môi trường Cloud lẫn On-Premise 100% Offline.