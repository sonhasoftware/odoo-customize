from datetime import datetime

from odoo import models, fields, api, _
import base64
from docx import Document
import io
import tempfile
import os


class HrContract(models.Model):
    _inherit = 'hr.contract'

    #
    contract_type_id = fields.Many2one('hr.contract.type', string="Loại hợp đồng", ondelete='cascade')

    def action_confirm(self):
        for r in self:
            if r.state == 'draft':
                r.state = 'open'

    def action_cancel(self):
        for r in self:
            if r.state == 'draft':
                r.state = 'cancel'

    def cancel_confirm(self):
        for r in self:
            if r.state == 'open':
                r.state = 'draft'

    def export_contract(self):
        dt_now = datetime.now()
        file_data = base64.b64decode(self.contract_type_id.file)

        # Tạo file tạm thời
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_file:
            tmp_file.write(file_data)
            tmp_file_path = tmp_file.name

        try:
            # Mở file Word từ đường dẫn tạm thời
            doc = Document(tmp_file_path)

            # Thay thế các biến với dữ liệu thực tế
            for paragraph in doc.paragraphs:
                if '[name_contract]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[name_contract]', self.name)
                if '[date]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[date]', str(dt_now.day))
                if '[month]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[month]', str(dt_now.month))
                if '[year]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[year]', str(dt_now.year))
                if '[name]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[name]', self.employee_id.name)
                if '[date_of_birth]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[date_of_birth]', str(self.employee_id.date_birthday.strftime("%d/%m/%Y")) or '')
                if '[permanent_address]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[permanent_address]', self.employee_id.permanent_address or '')
                if '[cccd]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[cccd]', str(self.employee_id.number_cccd) or '')
                if '[date_cccd]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[date_cccd]', str(self.employee_id.date_cccd.strftime("%d/%m/%Y")) or '')
                if '[cccd_nc]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[cccd_nc]', self.employee_id.place_of_issue or '')
                if '[phone]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[phone]', str(self.employee_id.mobile_phone) or '')
                if '[job_position]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[job_position]', self.job_id.name or '')
                if '[department]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[department]', self.department_id.name or '')
                if '[date_contract]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[date_contract]', str(self.date_start.strftime("%d/%m/%Y")) or '')
                if '[end_date_contract]' in paragraph.text:
                    paragraph.text = paragraph.text.replace('[end_date_contract]', str(self.date_end.strftime("%d/%m/%Y")) or '')
            # Lưu tài liệu vào bộ nhớ
            file_stream = io.BytesIO()
            doc.save(file_stream)
            file_stream.seek(0)

            # Lưu vào attachments
            attachment = self.env['ir.attachment'].create({
                'name': f'Hợp Đồng {self.name}.docx',  # Sử dụng trường name
                'type': 'binary',
                'datas': base64.b64encode(file_stream.read()),
                'res_model': 'hr.contract',
                'res_id': self.id,
            })

            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/{attachment.id}?download=true',
                'target': 'self',
            }
        finally:
            # Xóa file tạm thời
            os.remove(tmp_file_path)

