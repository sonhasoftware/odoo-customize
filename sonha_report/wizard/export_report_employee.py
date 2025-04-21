from odoo import models, fields
from odoo.exceptions import UserError, ValidationError
import base64
import io
import tempfile
import os
from openpyxl import load_workbook


class ExportReportEmployee(models.TransientModel):
    _name = 'export.report.employee'

    report = fields.Many2one('config.template.report', string="Chọn báo cáo")
    template_file = fields.Binary("Tệp Excel")

    def action_export(self):
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            raise ValidationError("Không có bản ghi nào được chọn.")

        list_record = self.env['sonha.employee.report'].browse(active_ids)
        file_stream = io.BytesIO(base64.b64decode(self.report.file))
        wb = load_workbook(filename=file_stream)
        sheet = wb['Sheet1']
        stt = 1
        row = 7
        for record in list_record:
            sheet.cell(row=row, column=1).value = stt
            sheet.cell(row=row, column=2).value = record.employee_code or ''
            sheet.cell(row=row, column=3).value = record.name or ''
            sheet.cell(row=row, column=4).value = record.employee_code or ''
            sheet.cell(row=row, column=5).value = str(record.onboard) or ''
            sheet.cell(row=row, column=6).value = str(record.onboard) or ''
            sheet.cell(row=row, column=7).value = record.employee_code or ''
            sheet.cell(row=row, column=8).value = record.employee_code or ''
            sheet.cell(row=row, column=9).value = record.department_id.name or ''
            sheet.cell(row=row, column=10).value = record.job_id.name or ''
            sheet.cell(row=row, column=11).value = record.employee_code or ''
            sheet.cell(row=row, column=12).value = record.employee_code or ''
            sheet.cell(row=row, column=13).value = record.employee_code or ''
            sheet.cell(row=row, column=14).value = record.employee_code or ''
            sheet.cell(row=row, column=15).value = str(record.date_birthday) or ''
            sheet.cell(row=row, column=16).value = record.employee_code or ''
            sheet.cell(row=row, column=17).value = record.employee_code or ''
            sheet.cell(row=row, column=18).value = record.employee_code or ''
            sheet.cell(row=row, column=19).value = record.employee_code or ''
            sheet.cell(row=row, column=20).value = record.employee_code or ''
            sheet.cell(row=row, column=21).value = record.employee_code or ''
            sheet.cell(row=row, column=22).value = record.employee_code or ''
            sheet.cell(row=row, column=23).value = record.employee_code or ''
            sheet.cell(row=row, column=24).value = record.employee_code or ''
            sheet.cell(row=row, column=25).value = record.employee_code or ''
            sheet.cell(row=row, column=26).value = record.employee_code or ''
            sheet.cell(row=row, column=27).value = record.employee_code or ''
            sheet.cell(row=row, column=28).value = record.employee_code or ''
            sheet.cell(row=row, column=29).value = record.employee_code or ''
            sheet.cell(row=row, column=30).value = record.employee_code or ''
            sheet.cell(row=row, column=31).value = record.employee_code or ''
            sheet.cell(row=row, column=31).value = record.employee_code or ''
            # Thêm các cột khác nếu cần
            row += 1
            stt += 1

            # Lưu lại file kết quả
        output_stream = io.BytesIO()
        wb.save(output_stream)
        output_stream.seek(0)

        # Trả về file để tải về
        export_file = base64.b64encode(output_stream.read())
        download_filename = f"{self.report.name}.xlsx"
        self.template_file = export_file

        # Tạo record ảo chỉ để tải file
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/export.report.employee/{self.id}/template_file/{download_filename}?download=true",
            'target': 'self',
        }
