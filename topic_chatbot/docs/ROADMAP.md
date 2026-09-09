# Lộ trình Phát triển Module (ROADMAP)

Tài liệu này theo dõi tiến độ các giai đoạn phát triển, các tính năng đã hoàn thiện và định hướng mở rộng tương lai cho module `topic_chatbot`.

---

## 📊 Bảng Tiến độ Tổng quan (Roadmap Status)

| Phase | Mục tiêu & Hạng mục | Ưu tiên | Trạng thái | Ghi chú & Phiên bản |
|:---:|:---|:---:|:---:|:---|
| **Phase 1** | **Technical Debt Cleanup** | P0 | **Hoàn thành** ✅ | v17.0.1.0.0 (Giảm code trùng, sửa admin rule, GIN index FTS, attachment=True) |
| **Phase 2** | **Production Hardening** | P0 | **Hoàn thành** ✅ | v17.0.1.1.0 (Async document processing, token character limit, rate limiting) |
| **Phase 3** | **Quality & Test Automation** | P1 | **Hoàn thành** ✅ | v17.0.1.2.0 (105 unit & integration tests, timezone UTC fix, mock controller) |
| **Phase 4** | **Polish & Localization** | P2 | **Hoàn thành** ✅ | v17.0.1.3.0 (i18n tiếng Việt, auto conversation title, smart stop words) |
| **Phase 5** | **Parent-Child RAG & PgVector** | P0 | **Hoàn thành** ✅ | v17.0.2.0.0 (Parent-Child chunking, PgVector HNSW 768, Gemini Embedding 2) |
| **Phase 6** | **Adaptive OCR & Excel Semantic Parser** | P0 | **Hoàn thành** ✅ | v17.0.2.0.0 (Gemini Vision slicing OCR cho bảng rộng, Excel RACI transformation) |
| **Phase 7** | **SQL Server Tool & Fernet Encryption** | P0 | **Hoàn thành** ✅ | v17.0.2.0.0 (MSSQL integration, Fernet AES-128 crypto, T-SQL whitelist & CTE) |
| **Phase 8** | **Advanced Hybrid Search & HyDE** | P0 | **Hoàn thành** ✅ | v17.0.2.0.0 (Hybrid Search RRF k=60, Selective HyDE, Metadata Filtering, Neighbor Expansion) |
| **Phase 9** | **Gemini Next-Gen Model Normalization** | P1 | **Hoàn thành** ✅ | v17.0.2.0.0 (Hỗ trợ Gemini 3.6 Flash, 3.5 Flash, 3.1 Pro Preview, Auto Deprecation Map) |
| **Phase 10**| **Service-Oriented Architecture & Thin Controller** | P0 | **Hoàn thành** ✅ | v17.0.2.0.0 (Tách controllers/main.py 2805 dòng -> 229 dòng, tạo services/ & utils/, Facade delegation) |
| **Phase 11**| **Dual-Vector Architecture & Local Ollama Integration** | P0 | **Hoàn thành** ✅ | v17.0.2.1.0 (Dual-Vector 768, Ollama nomic-embed-text, 2 chế độ độc lập, Auto-Fallback mượt mà) |
| **Phase 12**| **Future Innovations & Extensions** | P2 | **Định hướng** ⏳ | Cross-Encoder Re-ranker, Multi-turn SQL Self-Correction, Xuất PDF/Word Chat |

---

## 📌 Chi tiết các Hạng mục Tính năng Đã Triển Khai

### 1. Quản lý Tài liệu & Ingestion Engine
- [x] Hỗ trợ 6 định dạng tài liệu phổ biến: PDF, DOCX, XLSX, XLS, CSV, TXT.
- [x] Quản lý trạng thái vòng đời tài liệu: `Draft` -> `Processing` -> `Done` / `Partial` / `Error`.
- [x] Xử lý tài liệu nền (Background Daemon Thread) không làm đơ giao diện.
- [x] Cơ chế Cron Scheduled Actions tự động quét và phục hồi tài liệu bị treo.
- [x] Adaptive Gemini Vision OCR cho PDF scan và bảng rộng nhiều cột (slicing & merge JSON).
- [x] Phân tích ngữ nghĩa Excel và ma trận phân quyền/trách nhiệm RACI.
- [x] Quét cảnh báo chống tấn công tiêm mã độc Prompt Injection (song ngữ Anh/Việt).

### 2. Kiến trúc Vector & Hybrid RAG Retrieval
- [x] Phân mảnh hai cấp **Parent-Child Chunking** (Parent 2000-3500 chars, Child 400-500 chars).
- [x] Tích hợp PostgreSQL Extension `pgvector` với chỉ mục HNSW Cosine Similarity.
- [x] Sinh Vector Embedding theo lô (Batching 10 chunks) với PostgreSQL Advisory Lock chống nghẽn quota.
- [x] Cơ chế "Bù Embedding" (`action_retry_failed_embeddings`) khi chạm trần rate limit.
- [x] Tự động viết lại câu truy vấn (Query Rewriting) và trích xuất Metadata Filters (`apply_year`, `doc_type`, `department`).
- [x] Tự động kích hoạt **Selective HyDE** (Hypothetical Document Embeddings) cho câu hỏi trừu tượng.
- [x] Thuật toán **True Hybrid Search** kết hợp 3 kênh (Vector, FTS tsvector, N-gram Keyphrase ILIKE) theo chuẩn **Reciprocal Rank Fusion (RRF $k=60$)**.
- [x] Mở rộng ngữ cảnh hai chiều (Bidirectional Neighbor Expansion: `seq ± 1`).
- [x] Gom nhóm ngữ cảnh Small-to-Big Parent Context nạp vào LLM.

### 3. Tích hợp Công cụ Dữ liệu (Tools / Function Calling)
- [x] Công cụ `query_odoo_data`: Tra cứu dữ liệu HR, Phòng ban, Kết quả KPI qua ORM an toàn.
- [x] Công cụ `query_sql_server_data`: Truy vấn dữ liệu thực tế từ Microsoft SQL Server bên ngoài.
- [x] Quản lý đa kết nối SQL Server (`mssql_connection`) và cấu hình hệ thống chung.
- [x] Mã hóa đối xứng mật khẩu Fernet (AES-128-CBC + HMAC-SHA256) KDF từ `database.secret`.
- [x] Tự động đồng bộ Schema bảng từ `INFORMATION_SCHEMA.COLUMNS`.
- [x] Kiểm soát an toàn T-SQL (Chỉ cho phép SELECT/CTE, chặn đa lệnh `;`, chặn từ khóa cấm, tự động chèn `TOP 100`).
- [x] Nhật ký truy vấn SQL Server (`mssql_log`) ghi nhận thời gian thực thi (ms).
- [x] Bộ lọc tự động khử thuật ngữ kỹ thuật (Output Sanitization) sang ngôn ngữ nghiệp vụ tiếng Việt.

### 4. Giao diện Người dùng & Streaming
- [x] Giao diện Owl Component toàn màn hình hiện đại kiểu ChatGPT.
- [x] Real-time Streaming Server-Sent Events (SSE) mượt mà từng ký tự.
- [x] Hiển thị trạng thái tương tác động khi AI đang thực thi Tool truy vấn cơ sở dữ liệu.
- [x] Tự động đặt tên tiêu đề cuộc hội thoại theo 40 ký tự đầu của tin nhắn.
- [x] Hỗ trợ Markdown rendering đầy đủ (Bảng biểu, In đậm, Bullet points, Code blocks).
- [x] Chống spam với cơ chế Rate Limiting (5 tin nhắn/phút) và khóa cờ `is_processing`.

### 5. Kiến trúc Module & Tầng Dịch vụ (Service Layer)
- [x] Tách God Controller (`controllers/main.py`: 2,805 dòng) thành Thin Controller (229 dòng).
- [x] Tách toàn bộ AI RAG Pipeline sang `services/rag_engine.py` (818 dòng).
- [x] Tách NL2SQL & MSSQL Engine sang `services/sql_engine.py` (277 dòng).
- [x] Tách Query Rewriter & HyDE sang `services/query_rewriter.py` (160 dòng).
- [x] Tách System Instruction & Output Sanitization sang `services/prompt_builder.py` (240 dòng).
- [x] Gom luồng chat chung vào `services/chat_service.py` (535 dòng), loại bỏ trùng lặp code giữa `ask` và `ask_stream`.
- [x] Duy trì 100% tương thích ngược thông qua Delegation Wrappers trên `TopicChatbotController`.

### 6. Kiến trúc Dual-Vector & Tích hợp Ollama Local (On-Premise)
- [x] Nâng cấp CSDL với cột `embedding_vector_ollama vector(768)` và HNSW Cosine Index riêng biệt.
- [x] Xây dựng `services/embedding_service.py` điều phối embedding giữa Gemini Cloud và Ollama Local (`nomic-embed-text`).
- [x] Hỗ trợ 2 chế độ độc lập: Chế độ Gemini (kèm Ollama Auto-Fallback khi cạn quota) và Chế độ Ollama (100% Local Offline).
- [x] Đảm bảo tính toàn vẹn toán học: Không bao giờ so sánh chéo giữa vector Gemini và vector Ollama.
- [x] Bổ sung giao diện Cài đặt và nút "Kiểm tra kết nối Ollama" (`action_test_ollama_connection`).

---

## 🔮 Định hướng Phát triển Tương lai (Phase 12)

1. **Multi-turn SQL Self-Correction Loop:**
   - Khi câu lệnh T-SQL đầu tiên bị lỗi cú pháp hoặc thiếu cột, Gemini tự động nhận thông điệp lỗi và viết lại câu truy vấn chính xác mà không cần người dùng hỏi lại.
2. **Local Cross-Encoder Re-ranker:**
   - Bổ sung bước chấm điểm tương quan ngữ nghĩa chuyên sâu bằng mô hình re-ranking nhẹ trước khi đưa vào prompt context.
3. **Export Lịch sử Hội thoại:**
   - Cho phép người dùng tải toàn bộ phiên chat ra file PDF hoặc Microsoft Word (.docx) được định dạng chuyên nghiệp.