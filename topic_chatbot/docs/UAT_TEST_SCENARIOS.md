# KỊCH BẢN KIỂM THỬ NGƯỜI DÙNG (USER ACCEPTANCE TEST - UAT)
**Phân hệ:** Topic Chatbot (RAG)  
**Phiên bản:** `17.0.2.0.0`  
**Ngày lập:** 30/07/2026  

---

## 📋 DANH SÁCH CÁC KỊCH BẢN KIỂM THỬ (TEST SCENARIOS)

| STT | Kịch bản (Scenario) | Đối tượng thử nghiệm | Mục tiêu kiểm thử |
|:---:|:--------------------|:--------------------|:------------------|
| **TC-01** | Tạo Topic & Upload tài liệu (DOCX/TXT) | Admin / Topic Manager | Kiểm tra việc khởi tạo Topic và xử lý tài liệu bất đồng bộ (`Draft` → `Done`). |
| **TC-02** | Trả lời dựa trên tài liệu RAG & Auto-title | Người dùng cuối (End User) | Kiểm tra AI trích xuất đúng nội dung tài liệu, ghi rõ nguồn và tự đổi tên hội thoại. |
| **TC-03** | Truy vấn dữ liệu thực tế Odoo (KPI, Nhân sự) | End User (Có quyền xem) | Kiểm tra Function Calling tra cứu dữ liệu Odoo và ẩn thuật ngữ kỹ thuật. |
| **TC-04** | Kiểm tra Rate Limit & Chống lạm dụng | End User | Kiểm tra cơ chế chặn spam (tối đa 5 câu/phút) và chặn gửi dồn dập. |
| **TC-05** | Phân quyền Bảo mật (Security & Access Rules) | User & Administrator | Kiểm tra quyền xem cuộc hội thoại, Topic riêng tư và phân quyền Admin. |
| **TC-06** | Cấu hình Custom Stop Words & Cấu hình API | Administrator | Kiểm tra giao diện Cấu hình trong Settings và tùy chỉnh từ dừng. |

---

## 🛠️ CHI TIẾT KỊCH BẢN KIỂM THỬ

### 🔹 TC-01: Tạo Topic & Upload tài liệu (Async Document Processing)
* **Vài trò:** Administrator / Topic Manager  
* **Tiền đề (Pre-condition):** Tài khoản đăng nhập có quyền `Topic Chatbot / Administrator`.  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái (Pass/Fail) |
|:---:|:------------------|:-----------------------------------|:----------------------|
| 1 | Truy cập menu **Topic Chatbot** → **Topics**. Bấm **Tạo mới** (Create). | Giao diện tạo Topic hiển thị rõ ràng. | [ ] Pass |
| 2 | Nhập Tên: `Quy trình Nhân sự 2026`, chọn `Công khai = True`. Bấm Lưu. | Topic được lưu thành công. | [ ] Pass |
| 3 | Thêm một tài liệu PDF hoặc DOCX (ví dụ: `Huong_dan_thu_viec.pdf`) vào tab **Documents**. Bấm Lưu. | Tài liệu được tạo với trạng thái **`Draft` (Nháp)** lập tức mà không bị đơ UI. | [ ] Pass |
| 4 | Chờ 1 phút (hoặc vào *Scheduled Actions* bấm Run Manually cron job `Topic Chatbot: Process Documents`). | Trạng thái tài liệu chuyển sang **`Done` (Hoàn thành)**. Tab **Chunks** tự động sinh các đoạn văn bản băm nhỏ. | [ ] Pass |

---

### 🔹 TC-02: Hỏi đáp RAG & Tự động đặt tên hội thoại
* **Vai trò:** End User  
* **Tiền đề:** Đã có Topic `Quy trình Nhân sự 2026` ở trạng thái `Done`.  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái (Pass/Fail) |
|:---:|:------------------|:-----------------------------------|:----------------------|
| 1 | Truy cập menu **Topic Chatbot** → **Chatbot** (Giao diện OWL full-screen). | Màn hình Chatbot hiển thị danh sách Topic ở cột bên trái và khung chat bên phải. | [ ] Pass |
| 2 | Chọn Topic `Quy trình Nhân sự 2026`. Bấm **Hội thoại mới** (`+ New Chat`). | Tạo cuộc hội thoại mới có tên ban đầu là `New Chat` (hoặc `Cuộc trò chuyện mới`). | [ ] Pass |
| 3 | Gửi câu hỏi liên quan đến file đã upload (Ví dụ: *"Thời gian thử việc đối với nhân viên mới là bao lâu?"*). | - AI trả lời chính xác thông tin có trong file.<br>- Cuối câu trả lời có trích dẫn nguồn (VD: `Nguồn: Huong_dan_thu_viec.pdf`). | [ ] Pass |
| 4 | Quan sát danh sách cuộc hội thoại ở cột trái. | Tên cuộc hội thoại `New Chat` tự động chuyển thành câu hỏi của người dùng (VD: `Thời gian thử việc đối với...`). | [ ] Pass |

---

### 🔹 TC-03: Tra cứu dữ liệu Odoo thực tế & Chuẩn hóa văn phong
* **Vai trò:** End User (Nội bộ)  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái (Pass/Fail) |
|:---:|:------------------|:-----------------------------------|:----------------------|
| 1 | Mở khung Chatbot, nhập câu hỏi: *"Cho tôi biết danh sách nhân viên thuộc Phòng Kế toán"*. | AI gọi công cụ `query_odoo_data` và trả về danh sách nhân viên phòng Kế toán thực tế trong DB. | [ ] Pass |
| 2 | Đặt câu hỏi về KPI: *"Điểm đánh giá KPI tháng gần nhất của Nguyễn Văn A là bao nhiêu?"*. | AI truy vấn dữ liệu KPI và trình bày dưới dạng bảng/bullet gọn gàng. | [ ] Pass |
| 3 | Kiểm tra câu trả lời của AI. | AI **tuyệt đối không** để lộ các tên kỹ thuật như `hr.employee`, `hr.department`, `department_id`, `create_uid` mà dùng từ ngữ nghiệp vụ (Nhân viên, Phòng ban...). | [ ] Pass |

---

### 🔹 TC-04: Kiểm tra Rate Limit & Giới hạn Token bối cảnh
* **Vai trò:** End User (Kiểm thử tải & chống lạm dụng)  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái (Pass/Fail) |
|:---:|:------------------|:-----------------------------------|:----------------------|
| 1 | Gửi liên tục **6 câu hỏi** khác nhau trong vòng chưa đầy 1 phút. | Đến câu thứ 6, hệ thống trả về thông báo lỗi: *"Bạn đã gửi quá 5 câu hỏi trong vòng 1 phút. Vui lòng chờ một lát rồi thử lại."* | [ ] Pass |
| 2 | Trong khi AI đang sinh câu trả lời cho một câu hỏi, nhanh tay bấm gửi thêm 1 câu nữa. | Hệ thống báo lỗi: *"Vui lòng chờ câu trả lời trước hoàn tất..."* và nút Send bị vô hiệu hóa. | [ ] Pass |
| 3 | Tiếp tục chat trong một hội thoại rất dài (trên 30 tin nhắn văn bản dài). | AI vẫn trả lời mượt mà, nhớ bối cảnh các tin nhắn gần nhất mà không bị văng lỗi `MAX_TOKENS`. | [ ] Pass |

---

### 🔹 TC-05: Kiểm tra Phân quyền Bảo mật (Security & Access Rules)
* **Vai trò:** User thường vs Administrator  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái (Pass/Fail) |
|:---:|:------------------|:-----------------------------------|:----------------------|
| 1 | Đăng nhập bằng **User thường** (không có quyền Admin Chatbot). Mở danh sách Hội thoại. | User chỉ nhìn thấy các cuộc hội thoại do chính mình tạo ra. | [ ] Pass |
| 2 | Đăng nhập bằng **User thường**, tạo một Topic mới (`Topic Cá Nhân`). Thử tích chọn `Công khai = True`. | Hệ thống chặn không cho lưu và báo lỗi phân quyền (Chỉ Admin mới được tạo/sửa Topic công khai). | [ ] Pass |
| 3 | Đăng nhập bằng **Admin**. Truy cập danh sách Hội thoại. | Admin có thể nhìn thấy và audit toàn bộ hội thoại của tất cả người dùng trên hệ thống. | [ ] Pass |

---

### 🔹 TC-06: Cấu hình Từ dừng (Custom Stop Words) & Gemini Settings
* **Vai trò:** Administrator  

| Bước | Thao tác (Action) | Kết quả mong đợi (Expected Result) | Trạng thái (Pass/Fail) |
|:---:|:------------------|:-----------------------------------|:----------------------|
| 1 | Vào **Topic Chatbot** → **Configuration** → **Settings**. | Hiển thị các ô cấu hình `Gemini API Key`, `Gemini Model` và `Custom Stop Words`. | [ ] Pass |
| 2 | Nhập vào ô Custom Stop Words: `xin, chao, giup, voi, a`. Bấm **Save**. | Cấu hình được ghi nhận vào `ir.config_parameter`. | [ ] Pass |
| 3 | Đặt câu hỏi bắt đầu bằng các từ dừng trên (VD: *"Xin chào giúp tôi tra cứu chính sách"*). | Thuật toán RAG lọc bỏ các từ dừng trên và chỉ tìm kiếm từ khóa ý nghĩa (*"chính sách"*), trả về tài liệu chính xác. | [ ] Pass |

---

## 🎯 BÁO CÁO KẾT QUẢ UAT (UAT SIGN-OFF TEMPLATE)

* **Tổng số kịch bản:** 6 Scenarios (20 Test Steps)
* **Số bước đạt (Passed):** _____ / 20
* **Số bước lỗi (Failed):** _____ / 20
* **Người thực hiện kiểm thử:** _______________________
* **Ngày kiểm thử:** _____/_____/2026
* **Ý kiến đánh giá chung:** ____________________________________________________________________
