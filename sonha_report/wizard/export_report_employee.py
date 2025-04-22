from odoo import models, fields
from odoo.exceptions import UserError, ValidationError
import base64
import io
import tempfile
import os
from openpyxl.styles import Border, Side, Alignment
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
        if self.report.key == "bdns":
            row = 7
        elif self.report.key == "nsct":
            row = 12
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        center_alignment = Alignment(horizontal='center', vertical='center')
        for record in list_record:
            if self.report.key == "bdns":
                sheet.cell(row=row, column=1).value = stt
                sheet.cell(row=row, column=2).value = record.employee_code or ''
                sheet.cell(row=row, column=3).value = record.name or ''
                sheet.cell(row=row, column=4).value = ''
                sheet.cell(row=row, column=5).value = str(record.onboard) or ''
                sheet.cell(row=row, column=6).value = record.onboard.day or ''
                sheet.cell(row=row, column=7).value = record.onboard.month or ''
                sheet.cell(row=row, column=8).value = record.onboard.year or ''
                sheet.cell(row=row, column=9).value = record.department_id.name or ''
                sheet.cell(row=row, column=10).value = record.job_id.name or ''
                sheet.cell(row=row, column=11).value = ''
                sheet.cell(row=row, column=12).value = ''
                sheet.cell(row=row, column=13).value = ''
                sheet.cell(row=row, column=14).value = record.culture_level or ''
                sheet.cell(row=row, column=15).value = str(record.date_birthday) or ''
                sheet.cell(row=row, column=16).value = record.date_birthday.year or ''
                sheet.cell(row=row, column=17).value = ''
                sheet.cell(row=row, column=18).value = record.seniority_display or ''
                sheet.cell(row=row, column=19).value = record.seniority_display or ''
                sheet.cell(row=row, column=20).value = record.marital_status or ''
                sheet.cell(row=row, column=21).value = record.number_cccd or ''
                sheet.cell(row=row, column=22).value = record.permanent or ''
                sheet.cell(row=row, column=23).value = ''
                sheet.cell(row=row, column=24).value = ''
                sheet.cell(row=row, column=25).value = ''
                sheet.cell(row=row, column=26).value = str(record.date_quit) or ''
                sheet.cell(row=row, column=27).value = record.date_quit.day if record.date_quit else ''
                sheet.cell(row=row, column=28).value = record.date_quit.month if record.date_quit else ''
                sheet.cell(row=row, column=29).value = record.date_quit.year if record.date_quit else ''
                sheet.cell(row=row, column=30).value = record.work_email or ''
                sheet.cell(row=row, column=31).value = str(record.sonha_number_phone) or ''
            elif self.report.key == "nsct":
                sheet.cell(row=row, column=1).value = stt
                sheet.cell(row=row, column=2).value = record.device_id_num or ''
                sheet.cell(row=row, column=3).value = record.employee_code or ''
                sheet.cell(row=row, column=4).value = record.name
                sheet.cell(row=row, column=5).value = str(record.onboard) or ''
                sheet.cell(row=row, column=6).value = str(record.reception_date) or ''
                sheet.cell(row=row, column=7).value = record.job_id.name or ''
                sheet.cell(row=row, column=8).value = record.department_id.name or ''
                sheet.cell(row=row, column=9).value = record.gender or ''
                sheet.cell(row=row, column=10).value = str(record.date_birthday) or ''
                sheet.cell(row=row, column=11).value = record.marital_status or ''
                sheet.cell(row=row, column=12).value = record.nation or ''
                sheet.cell(row=row, column=13).value = record.religion or ''
                sheet.cell(row=row, column=14).value = record.hometown or ''
                sheet.cell(row=row, column=15).value = record.permanent or ''
                sheet.cell(row=row, column=16).value = record.permanent or ''
                sheet.cell(row=row, column=17).value = record.sonha_number_phone or ''
                sheet.cell(row=row, column=18).value = record.number_cccd or ''
                sheet.cell(row=row, column=19).value = str(record.date_cccd) or ''
                sheet.cell(row=row, column=20).value = record.place_of_issue or ''
                sheet.cell(row=row, column=21).value = record.tax_code or ''
                sheet.cell(row=row, column=22).value = 'Bậc nhân sự'
                sheet.cell(row=row, column=23).value = record.seniority_display
                sheet.cell(row=row, column=24).value = ''
                sheet.cell(row=row, column=25).value = ''
                sheet.cell(row=row, column=26).value = ''
                sheet.cell(row=row, column=27).value = ''
                sheet.cell(row=row, column=28).value = ''

            row += 1
            stt += 1

            # Lưu lại file kết quả
        for row in sheet.iter_rows(min_row=1, max_row=sheet.max_row, min_col=1, max_col=sheet.max_column):
            for cell in row:
                cell.border = thin_border
                cell.alignment = center_alignment
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
