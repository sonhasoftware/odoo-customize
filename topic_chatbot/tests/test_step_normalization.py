# -*- coding: utf-8 -*-
import unittest
from ..services.prompt_builder import (
    normalize_step_lists,
    bold_ui_action_terms,
)


class TestStepNormalization(unittest.TestCase):
    """Unit tests for normalize_step_lists and bold_ui_action_terms."""

    # -------------------------------------------------------------
    # Tests for normalize_step_lists
    # -------------------------------------------------------------
    def test_01_asterisk_steps_renumbered_and_bolded(self):
        """Case 1: Input uses '*' for all steps (e.g. 'Tạo Duyệt giá' with 4 steps)."""
        input_text = (
            "### Tạo Duyệt giá\n"
            "* Bước 1: Vào menu Mua hàng -> Đơn hàng -> Duyệt giá -> Nhấn Tạo\n"
            "* Bước 2: Tại màn hình Duyệt giá mới, người dùng điền các trường thông tin\n"
            "* Bước 3: Sau khi nhập xong các trường thông tin -> Nhấn Lưu để lưu lại\n"
            "* Bước 4: Nhấn Gửi duyệt để gửi thông báo duyệt giá đến các cấp duyệt"
        )
        expected_output = (
            "### Tạo Duyệt giá\n"
            "1. **Bước 1**: Vào menu **Mua hàng** -> **Đơn hàng** -> **Duyệt giá** -> Nhấn **Tạo**\n"
            "2. **Bước 2**: Tại màn hình Duyệt giá mới, người dùng điền các trường thông tin\n"
            "3. **Bước 3**: Sau khi nhập xong các trường thông tin -> Nhấn **Lưu** để lưu lại\n"
            "4. **Bước 4**: Nhấn **Gửi duyệt** để gửi thông báo duyệt giá đến các cấp duyệt"
        )
        result = normalize_step_lists(input_text)
        self.assertEqual(result, expected_output)

    def test_02_dash_steps_out_of_order_renumbered(self):
        """Case 2: Input uses '-' for steps, out of order (Bước 1, Bước 3, Bước 2).
        Must be renumbered sequentially to 1, 2, 3 based on appearance.
        """
        input_text = (
            "- Bước 1: Đăng nhập vào hệ thống\n"
            "- Bước 3: Điền thông tin phiếu\n"
            "- Bước 2: Nhấn nút Lưu"
        )
        expected_output = (
            "1. **Bước 1**: Đăng nhập vào hệ thống\n"
            "2. **Bước 2**: Điền thông tin phiếu\n"
            "3. **Bước 3**: Nhấn nút **Lưu**"
        )
        result = normalize_step_lists(input_text)
        self.assertEqual(result, expected_output)

    def test_03_two_separate_step_clusters_reset_numbering(self):
        """Case 3: Input has 2 separate step clusters separated by heading '###'.
        Each cluster must reset and number from 1.
        """
        input_text = (
            "### Quy trình 1\n"
            "* Bước 1: Thao tác A\n"
            "* Bước 2: Thao tác B\n\n"
            "### Quy trình 2\n"
            "* Bước 1: Thao tác C\n"
            "* Bước 2: Thao tác D"
        )
        expected_output = (
            "### Quy trình 1\n"
            "1. **Bước 1**: Thao tác A\n"
            "2. **Bước 2**: Thao tác B\n\n"
            "### Quy trình 2\n"
            "1. **Bước 1**: Thao tác C\n"
            "2. **Bước 2**: Thao tác D"
        )
        result = normalize_step_lists(input_text)
        self.assertEqual(result, expected_output)

    def test_04_no_steps_plain_text_unchanged(self):
        """Case 4: Input has no steps (plain text paragraphs) -> returns unchanged."""
        input_text = (
            "Chào bạn, tôi là trợ lý AI.\n"
            "Tôi có thể hỗ trợ bạn tra cứu quy trình tờ trình và hướng dẫn sử dụng.\n"
            "Vui lòng gửi câu hỏi nếu bạn cần giúp đỡ."
        )
        result = normalize_step_lists(input_text)
        self.assertEqual(result, input_text)

    def test_05_already_numbered_steps_not_duplicated(self):
        """Case 5: Input already formatted with numbers ('1. 2. 3.') -> not duplicated or renumbered."""
        input_text = (
            "1. **Bước 1**: Thao tác A\n"
            "2. **Bước 2**: Thao tác B\n"
            "3. **Bước 3**: Thao tác C"
        )
        result = normalize_step_lists(input_text)
        self.assertEqual(result, input_text)

    def test_06_markdown_tables_and_code_blocks_preserved(self):
        """Test that Markdown table lines and code blocks are not modified."""
        input_text = (
            "### Bảng và Code\n"
            "| Cột 1 | Cột 2 |\n"
            "| --- | --- |\n"
            "| * Bước 1: Giá trị | Không đổi |\n\n"
            "```python\n"
            "* Bước 1: code test\n"
            "- Bước 2: code test\n"
            "```\n"
            "* Bước 1: Thao tác thật"
        )
        result = normalize_step_lists(input_text)
        self.assertIn("| * Bước 1: Giá trị | Không đổi |", result)
        self.assertIn("* Bước 1: code test", result)
        self.assertIn("1. **Bước 1**: Thao tác thật", result)

    def test_07_actual_case_import_duyet_gia_6_steps(self):
        """Test actual case 'Import Duyệt giá' with 6 steps using '*'."""
        input_text = (
            "### Import Duyệt giá\n"
            "* Bước 1: Vào menu Mua hàng -> Đơn hàng -> Duyệt giá\n"
            "* Bước 2: Nhấn nút Import tại góc trên màn hình\n"
            "* Bước 3: Tải tệp mẫu và điền thông tin chi tiết duyệt giá\n"
            "* Bước 4: Nhấn Tải lên để tải file Excel lên hệ thống\n"
            "* Bước 5: Nhấn Kiểm tra để kiểm tra tính hợp lệ của dữ liệu\n"
            "* Bước 6: Nhấn Nhập khẩu để hoàn tất import"
        )
        result = normalize_step_lists(input_text)
        for i in range(1, 7):
            self.assertIn(f"{i}. **Bước {i}**:", result)
        self.assertIn("Vào menu **Mua hàng** -> **Đơn hàng** -> **Duyệt giá**", result)
        self.assertIn("Nhấn nút **Import**", result)
        self.assertIn("Nhấn **Tải lên**", result)
        self.assertIn("Nhấn **Kiểm tra**", result)
        self.assertIn("Nhấn **Nhập khẩu**", result)

    # -------------------------------------------------------------
    # Tests for bold_ui_action_terms
    # -------------------------------------------------------------
    def test_08_bold_button_action(self):
        """Bold test 1: 'Nhấn nút Lưu' -> 'Nhấn nút **Lưu**'."""
        self.assertEqual(bold_ui_action_terms("Nhấn nút Lưu"), "Nhấn nút **Lưu**")
        self.assertEqual(bold_ui_action_terms("Nhấn Lưu"), "Nhấn **Lưu**")
        self.assertEqual(bold_ui_action_terms("Click nút Tạo"), "Click nút **Tạo**")
        self.assertEqual(bold_ui_action_terms("chọn Nhập hồ sơ"), "chọn **Nhập hồ sơ**")

    def test_09_bold_menu_path(self):
        """Bold test 2: 'Vào menu: Mua hàng → Đơn hàng → Duyệt giá'."""
        self.assertEqual(
            bold_ui_action_terms("Vào menu: Mua hàng → Đơn hàng → Duyệt giá"),
            "Vào menu: **Mua hàng** → **Đơn hàng** → **Duyệt giá**"
        )
        self.assertEqual(
            bold_ui_action_terms("Vào menu Mua hàng -> Đơn hàng -> Duyệt giá"),
            "Vào menu **Mua hàng** -> **Đơn hàng** -> **Duyệt giá**"
        )

    def test_10_already_bolded_not_doubled(self):
        """Bold test 3: Text with existing '**' must not be double bolded."""
        self.assertEqual(bold_ui_action_terms("Nhấn nút **Lưu**"), "Nhấn nút **Lưu**")
        self.assertEqual(bold_ui_action_terms("Nhấn **Lưu**"), "Nhấn **Lưu**")
        self.assertEqual(
            bold_ui_action_terms("Vào menu: **Mua hàng** → **Đơn hàng** → **Duyệt giá**"),
            "Vào menu: **Mua hàng** → **Đơn hàng** → **Duyệt giá**"
        )

    def test_11_empty_and_none_handling(self):
        """Test edge cases with empty string or None."""
        self.assertEqual(bold_ui_action_terms(""), "")
        self.assertIsNone(bold_ui_action_terms(None))
        self.assertEqual(normalize_step_lists(""), "")
        self.assertIsNone(normalize_step_lists(None))


if __name__ == '__main__':
    unittest.main()
