# KỊCH BẢN KIỂM THỬ CHẤP NHẬN NGƯỜI DÙNG (USER ACCEPTANCE TEST - UAT)
**Phân hệ:** Topic Chatbot (RAG & Enterprise AI Assistant)  
**Phiên bản:** `17.0.2.0.0`  
**Ngày cập nhật:** 25/08/2026  

---

## 📋 DANH SÁCH CÁC KỊCH BẢN KIỂM THỬ (TEST SCENARIOS)

| STT | Kịch bản (Scenario) | Đối tượng thử nghiệm | Mục tiêu kiểm thử |
|:---:|:--------------------|:--------------------|:------------------|
| **TC-01** | Tạo Topic & Upload tài liệu (Async Background Processing) | Admin / Topic Manager | Kiểm tra việc khởi tạo Topic, tải tệp (PDF/DOCX/Excel/TXT) và xử lý ngầm trong Daemon Thread (`Draft` → `Processing` → `Done`). |
| **TC-02** | Xử lý File PDF Scan & Bảng rộng (Gemini Vision OCR Slicing) | Admin | Kiểm tra Adaptive OCR Pipeline phân loại layout, cắt dọc ảnh bảng nhiều cột và trích xuất bảng Markdown nguyên vẹn. |
| **TC-03** | Xử lý File Excel Ma trận Phân quyền & RACI | Admin | Kiểm tra việc tự động phát hiện Header đa tầng và biến đổi từng dòng thành Bản ghi ngữ nghĩa tự mang thông tin (Semantic Records). |
| **TC-04** | Trả lời RAG (Parent-Child Strategy & Auto-title) | End User | Kiểm tra AI tìm kiếm qua vector Child Chunk, nạp ngữ cảnh Parent Chunk đầy đủ và tự động cập nhật tiêu đề hội thoại. |
| **TC-05** | Hybrid Search (RRF k=60) & Selective HyDE | End User | Kiểm tra khả năng trả lời chính xác các câu hỏi trừu tượng (*tại sao, so sánh, phân tích*) và câu hỏi từ khóa kỹ thuật. |
| **TC-06** | Bộ lọc Metadata nâng cao (Năm, Loại văn bản, Phòng ban) | End User | Kiểm tra LLM tự động trích xuất metadata và lọc SQL chính xác theo Năm áp dụng, Loại văn bản, Phòng ban. |
| **TC-07** | Bù Embedding khi bị Rate Limit (`Partial Embeddings`) | Admin | Kiểm tra tài liệu ở trạng thái `Partial Embeddings` và sử dụng nút "Bù Embedding" để bổ sung vector mà không cần parse lại file. |
| **TC-08** | Truy vấn Dữ liệu Odoo nội bộ (`query_odoo_data`) | End User | Kiểm tra AI Function Calling tra cứu Nhân viên, Phòng ban, Kết quả KPI và tự động che giấu thuật ngữ kỹ thuật. |
| **TC-09** | Kết nối & Truy vấn SQL Server (`query_sql_server_data`) | Admin & End User | Kiểm tra cấu hình kết nối đa máy chủ SQL Server, mã hóa mật khẩu Fernet, đồng bộ Schema và thực thi T-SQL an toàn. |
| **TC-10** | Kiểm tra An toàn & Bảo mật T-SQL (Strict Read-Only) | End User (Kiểm thử bảo mật) | Kiểm tra việc chặn các câu lệnh nguy hiểm (INSERT, UPDATE, DELETE, multi-statement `;`, truy cập bảng ngoài danh sách cho phép). |
| **TC-11** | Kiểm tra Rate Limit & Quản lý Token Context | End User (Kiểm thử tải) | Kiểm tra cơ chế chặn spam (5 tin nhắn/phút), chặn gửi dồn dập và giới hạn ký tự `MAX_CHARS=30000` trên hội thoại dài. |
| **TC-12** | Phân quyền Bảo mật (Security & Access Rules) | User & Administrator | Kiểm tra quyền truy cập Topic công khai / riêng tư, quyền truy vấn SQL Server và quyền xem lịch sử hội thoại của Admin. |

---

## 🛠️ CHI TIẾT CÁC BƯỚC THỰC HIỆN KIỂM THỬ

### 🔹 TC-01: Tạo Topic & Upload tài liệu (Async Background Processing)
* **Vai trò:** Administrator / Topic Manager  
* **Tiền đề:** Đăng nhập tài khoản có quyền `Topic Chatbot / Administrator`.

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Vào menu **Topic Chatbot** → **Topics** → Bấm **Tạo mới** (Create). | Giao diện form tạo Topic hiển thị. | [ ] Pass |
| 2 | Nhập Tên Topic: `Sổ tay Quy chế Doanh nghiệp 2026`, tích chọn `Công khai = True`. Bấm Lưu. | Topic được lưu thành công. | [ ] Pass |
| 3 | Trong tab **Documents**, bấm Thêm dòng và upload file DOCX/PDF. Bấm Lưu. | Bản ghi tài liệu xuất hiện với trạng thái **`Draft` (Nháp)** ngay lập tức mà không bị đơ UI. | [ ] Pass |
| 4 | Bấm nút **"Xử lý tài liệu"** (hoặc chờ Cron Job chạy ngầm 1 phút). | Trạng thái chuyển sang **`Processing`** rồi thành **`Done`**. Tab **Text Chunks** tự động sinh các Parent Chunks và Child Chunks kèm Vector. | [ ] Pass |

---

### 🔹 TC-02: Xử lý PDF Scan & Bảng rộng (Gemini Vision OCR Slicing)
* **Vai trò:** Administrator  
* **Tiền đề:** Đã cấu hình Gemini API Key hợp lệ.

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Upload một file PDF dạng scan hoặc chứa bảng dữ liệu rộng nhiều cột (>= 6 cột). | Hệ thống nhận diện tệp không có text layer đủ điều kiện và chuyển sang luồng Adaptive Vision OCR. | [ ] Pass |
| 2 | Bấm **"Xử lý tài liệu"** và quan sát trường `Layout Type`. | Trường `Layout Type` hiển thị `wide_table` hoặc `mixed`. | [ ] Pass |
| 3 | Xem nội dung trích xuất (`Extracted Text`). | Toàn bộ các cột trong bảng được trích xuất đầy đủ thành bảng Markdown, không bị mất cột hay lệch dòng. | [ ] Pass |

---

### 🔹 TC-03: Xử lý File Excel Ma trận Phân quyền & RACI
* **Vai trò:** Administrator  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Upload tệp Excel `.xlsx` chứa ma trận phân quyền (có các ký hiệu A, R, I, C, Duyệt...). Bấm Xử lý. | Trạng thái chuyển thành `Done`. | [ ] Pass |
| 2 | Bấm **"Xem các đoạn văn bản"** (Chunks). | Xuất hiện các Parent Chunks chứa tiêu đề bảng và các bản ghi ngữ nghĩa; Child Chunks gắn liền từng vai trò với trách nhiệm cụ thể. | [ ] Pass |

---

### 🔹 TC-04: Trả lời RAG (Parent-Child Strategy & Auto-title)
* **Vai trò:** End User  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Mở menu **Topic Chatbot** → **Chatbot** (Giao diện Owl toàn màn hình). | Dashboard hiển thị danh sách Topic ở cột trái và khung chat ở giữa. | [ ] Pass |
| 2 | Chọn Topic vừa tạo, bấm **`+ Cuộc trò chuyện mới`**. | Tạo phiên chat mới với tiêu đề mặc định. | [ ] Pass |
| 3 | Nhập câu hỏi liên quan đến nội dung tài liệu đã tải lên. | AI stream câu trả lời thời gian thực mượt mà, đầy đủ ngữ cảnh đoạn văn và trích dẫn nguồn rõ ràng. | [ ] Pass |
| 4 | Quan sát danh sách cuộc hội thoại ở thanh sidebar. | Tiêu đề cuộc hội thoại tự động đổi thành 40 ký tự đầu tiên của câu hỏi người dùng. | [ ] Pass |

---

### 🔹 TC-05: Hybrid Search (RRF k=60) & Selective HyDE
* **Vai trò:** End User  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Đặt câu hỏi trừu tượng: *"Tại sao doanh nghiệp cần áp dụng quy trình kiểm soát chất lượng mới?"*. | Hệ thống tự động kích hoạt Selective HyDE, tìm kiếm trúng các đoạn giải thích nguyên nhân và AI trả lời sâu sắc, đúng trọng tâm. | [ ] Pass |
| 2 | Đặt câu hỏi chứa mã hiệu/từ khóa chuyên môn: *"Theo điều 12.3 quy định mức phạt vi phạm là bao nhiêu?"*. | Thuật toán FTS và N-gram Keyphrase bắt chính xác điều khoản và AI trả lời đúng số liệu quy định. | [ ] Pass |

---

### 🔹 TC-06: Bộ lọc Metadata nâng cao (Năm, Loại văn bản, Phòng ban)
* **Vai trò:** End User  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Nhập câu hỏi: *"Cho tôi xem quy định của Phòng Kế toán năm 2025 về tạm ứng"*. | LLM viết lại câu truy vấn và trích xuất `{apply_year: 2025, doc_type: 'regulation', department: 'Kế toán'}` để lọc SQL chính xác. | [ ] Pass |
| 2 | Kiểm tra nguồn tài liệu AI trích dẫn. | Chỉ các tài liệu khớp đúng bộ lọc mới được nạp vào ngữ cảnh trả lời. | [ ] Pass |

---

### 🔹 TC-07: Bù Embedding khi bị Rate Limit (`Partial Embeddings`)
* **Vai trò:** Administrator  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Khi tài liệu ở trạng thái `Partial Embeddings` (do chạm hạn mức API 429). | Trên Form Document xuất hiện cảnh báo rõ ràng và nút **"Bù Embedding"**. | [ ] Pass |
| 2 | Bấm nút **"Bù Embedding"** (`action_retry_failed_embeddings`). | Hệ thống chỉ gọi API tạo vector cho các chunk còn thiếu; khi hoàn tất, trạng thái tài liệu tự động chuyển thành **`Done`**. | [ ] Pass |

---

### 🔹 TC-08: Truy vấn Dữ liệu Odoo nội bộ (`query_odoo_data`)
* **Vai trò:** End User  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Chọn Topic có bật `Hỏi dữ liệu DB (Odoo)`. Đặt câu hỏi: *"Danh sách nhân viên thuộc Phòng IT hiện tại"*. | Giao diện hiển thị thông báo trạng thái `Đang truy vấn cơ sở dữ liệu...`, AI gọi công cụ và trả về danh sách thực tế. | [ ] Pass |
| 2 | Kiểm tra nội dung phản hồi của AI. | AI trình bày bảng Markdown gọn gàng, tuyệt đối không lộ các từ ngữ kỹ thuật như `hr.employee`, `department_id`... | [ ] Pass |

---

### 🔹 TC-09: Kết nối & Truy vấn SQL Server (`query_sql_server_data`)
* **Vai trò:** Administrator & End User  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Vào **Topic Chatbot** → **Configuration** → **SQL Connections**. Tạo cấu hình kết nối SQL Server mới. Bấm **Test Connection**. | Thông báo kết nối thành công qua `pyodbc` / `pymssql` và hiển thị phiên bản SQL Server. Mật khẩu được mã hóa `tc_enc:...` trong DB. | [ ] Pass |
| 2 | Mở một Topic, bật `Hỏi dữ liệu SQL Server`, chọn kết nối trên, nhập danh sách bảng cho phép (`dbo.SanPham, dbo.TonKho`). Bấm **"Đồng bộ cấu trúc bảng"**. | Thông tin các cột và kiểu dữ liệu được tự động điền vào ô `Schema Info`. | [ ] Pass |
| 3 | Mở khung Chatbot với Topic trên, hỏi: *"Top 5 sản phẩm có giá bán cao nhất hiện nay"*. | AI sinh câu lệnh T-SQL SELECT hợp lệ, truy vấn SQL Server và trả về bảng giá sản phẩm chính xác. | [ ] Pass |

---

### 🔹 TC-10: Kiểm tra An toàn & Bảo mật T-SQL (Strict Read-Only)
* **Vai trò:** End User (Kiểm thử an ninh)  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Đặt câu hỏi mang tính phá hoại: *"Hãy xóa bảng sản phẩm giúp tôi"* hoặc *"Cập nhật giá sản phẩm thành 0"*. | Hệ thống chặn từ chối ngay lập tức vì vi phạm quy tắc chỉ đọc (Read-Only) và không thực thi câu lệnh SQL nguy hiểm. | [ ] Pass |
| 2 | Hỏi về bảng không nằm trong danh sách cho phép (ví dụ: bảng `dbo.NhanSu` chưa được whitelist). | Hệ thống chặn và thông báo bảng không nằm trong phạm vi cho phép của chủ đề. | [ ] Pass |

---

### 🔹 TC-11: Kiểm tra Rate Limit & Quản lý Token Context
* **Vai trò:** End User  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Gửi liên tục **6 câu hỏi** trong vòng dưới 1 phút. | Câu hỏi thứ 6 bị chặn với thông báo lỗi: *"Bạn đã gửi quá 5 câu hỏi trong vòng 1 phút. Vui lòng chờ một lát rồi thử lại."* | [ ] Pass |
| 2 | Bấm gửi câu hỏi mới trong khi câu trả lời trước đang sinh ký tự. | Nút Gửi bị khóa và hệ thống yêu cầu chờ câu trả lời trước hoàn tất. | [ ] Pass |
| 3 | Trò chuyện liên tục trong một hội thoại dài (> 30 tin nhắn). | Hệ thống kiểm soát tổng ký tự `MAX_CHARS=30000`, hội thoại diễn ra mượt mà không gặp lỗi `MAX_TOKENS`. | [ ] Pass |

---

### 🔹 TC-12: Phân quyền Bảo mật (Security & Access Rules)
* **Vai trò:** User thường vs Administrator  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái |
|:---:|:---|:---|:---:|
| 1 | Đăng nhập bằng **User thường**. Thử tạo Topic mới và tích chọn `Hỏi dữ liệu SQL Server` hoặc `Công khai`. | Hệ thống báo lỗi ValidationError (Chỉ Administrator mới có quyền bật các tính năng này). | [ ] Pass |
| 2 | Đăng nhập bằng **User thường**. Mở danh sách hội thoại. | User chỉ nhìn thấy các cuộc hội thoại của chính mình. | [ ] Pass |
| 3 | Đăng nhập bằng **Administrator**. Mở danh sách hội thoại. | Administrator có thể xem và audit toàn bộ hội thoại của tất cả user trên hệ thống. | [ ] Pass |

---

## 🎯 BIỂU MẪU KÝ DUYỆT NGHIỆM THU (UAT SIGN-OFF)

* **Tổng số kịch bản:** 12 Scenarios (30 Test Steps)
* **Kết quả kiểm thử:** Đạt _____ / 30 bước  
* **Đại diện Kiểm thử (QA / Senior Dev):** _______________________  
* **Đại diện Khách hàng / Product Owner:** _______________________  
* **Ngày ký duyệt:** _____ / _____ / 2026  
* **Đánh giá chung:** Module hoạt động ổn định, đáp ứng toàn diện các tiêu chuẩn bảo mật và nghiệp vụ doanh nghiệp.