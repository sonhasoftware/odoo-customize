from odoo import models, fields
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
from dateutil.relativedelta import relativedelta
import base64
import io
import tempfile
import os
from openpyxl.styles import Border, Side, Alignment
from openpyxl import load_workbook
from collections import defaultdict
from openpyxl.utils import get_column_letter


class ExportReportEmployee(models.TransientModel):
    _name = 'export.report.employee'

    report = fields.Many2one('config.template.report', string="Chọn báo cáo",
                             domain="[('apply', '=', res_model)]")
    template_file = fields.Binary("Tệp Excel")
    res_model = fields.Many2one('ir.model')

    def action_export(self):
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            raise ValidationError("Không có bản ghi nào được chọn.")

        list_record = self.env['sonha.employee.report'].browse(active_ids)
        file_stream = io.BytesIO(base64.b64decode(self.report.file))
        wb = load_workbook(filename=file_stream)
        sheet = wb['Sheet1']
        stt = 1
        if self.report.key == "bdns" or self.report.key == "ttc" or self.report.key == "nsthd":
            row = 7
            row_min = 6
        elif self.report.key == "nsct":
            row = 7
            row_min = 6
        elif self.report.key == "nsnv":
            row = 8
            row_min = 7
        elif self.report.key == "nvsn":
            row = 10
            row_min = 9
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        center_alignment = Alignment(horizontal='center', vertical='center')
        now = datetime.now().date()
        filter_report = self.env['popup.sonha.employee.report'].sudo().search([], order='id desc', limit=1)
        start_date = filter_report.from_date.strftime('%d/%m/%Y')
        end_date = filter_report.to_date.strftime('%d/%m/%Y')
        report_date = now.day
        report_month = now.month
        report_year = now.year
        for record in list_record:
            # Báo cáo biến động nhân sự
            if self.report.key == "bdns":
                date_birthday = record.date_birthday.strftime('%d/%m/%Y') if record.date_birthday else ""
                onboard = record.onboard.strftime('%d/%m/%Y') if record.onboard else ""
                contract_date_end = record.contract_id.date_end.strftime('%d/%m/%Y') if record.contract_id.date_end else ""
                date_quit = record.date_quit.strftime('%d/%m/%Y') if record.date_quit else ""
                age = relativedelta(now, record.date_birthday).years
                sheet.cell(row=row, column=1).value = stt
                sheet.cell(row=row, column=2).value = record.employee_code or ''
                sheet.cell(row=row, column=3).value = record.name or ''
                sheet.cell(row=row, column=4).value = ''
                sheet.cell(row=row, column=5).value = onboard
                sheet.cell(row=row, column=6).value = record.onboard.day or ''
                sheet.cell(row=row, column=7).value = record.onboard.month or ''
                sheet.cell(row=row, column=8).value = record.onboard.year or ''
                sheet.cell(row=row, column=9).value = record.department_id.name or ''
                sheet.cell(row=row, column=10).value = record.job_id.name or ''
                sheet.cell(row=row, column=11).value = ''
                sheet.cell(row=row, column=12).value = ''
                sheet.cell(row=row, column=13).value = ''
                sheet.cell(row=row, column=14).value = record.culture_level or ''
                sheet.cell(row=row, column=15).value = date_birthday
                sheet.cell(row=row, column=16).value = record.date_birthday.year or ''
                sheet.cell(row=row, column=17).value = age or ''
                sheet.cell(row=row, column=18).value = record.seniority_display or ''
                sheet.cell(row=row, column=19).value = record.seniority_display or ''
                sheet.cell(row=row, column=20).value = record.get_gender_label() or ''
                sheet.cell(row=row, column=21).value = record.number_cccd or ''
                sheet.cell(row=row, column=22).value = record.permanent or ''
                sheet.cell(row=row, column=23).value = ''
                sheet.cell(row=row, column=24).value = record.contract_id.contract_type_id.name or ''
                sheet.cell(row=row, column=25).value = contract_date_end
                sheet.cell(row=row, column=26).value = date_quit
                sheet.cell(row=row, column=27).value = record.date_quit.day if record.date_quit else ''
                sheet.cell(row=row, column=28).value = record.date_quit.month if record.date_quit else ''
                sheet.cell(row=row, column=29).value = record.date_quit.year if record.date_quit else ''
                sheet.cell(row=row, column=30).value = record.work_email or ''
                sheet.cell(row=row, column=31).value = str(record.sonha_number_phone) if record.sonha_number_phone else ''
            # Báo cáo nhân sự chi tiết
            elif self.report.key == "nsct":
                total_emp = str(len(active_ids))
                sheet.cell(row=5, column=3).value = sheet.cell(row=5, column=3).value.replace('[total_emp]', total_emp)
                reception_date = record.reception_date.strftime('%d/%m/%Y') if record.reception_date else ""
                onboard = record.onboard.strftime('%d/%m/%Y') if record.onboard else ""
                date_birthday = record.date_birthday.strftime('%d/%m/%Y') if record.date_birthday else ""
                date_cccd = record.date_cccd.strftime('%d/%m/%Y') if record.date_cccd else ""
                sheet.cell(row=row, column=1).value = stt
                sheet.cell(row=row, column=2).value = record.device_id_num or ''
                sheet.cell(row=row, column=3).value = record.employee_code or ''
                sheet.cell(row=row, column=4).value = record.name
                sheet.cell(row=row, column=5).value = onboard
                sheet.cell(row=row, column=6).value = reception_date
                sheet.cell(row=row, column=7).value = record.job_id.name or ''
                sheet.cell(row=row, column=8).value = record.department_id.name or ''
                sheet.cell(row=row, column=9).value = record.get_gender_label() or ''
                sheet.cell(row=row, column=10).value = date_birthday
                sheet.cell(row=row, column=11).value = record.get_marital_status_label() or ''
                sheet.cell(row=row, column=12).value = record.nation or ''
                sheet.cell(row=row, column=13).value = record.get_religion_label() or ''
                sheet.cell(row=row, column=14).value = record.hometown or ''
                sheet.cell(row=row, column=15).value = record.permanent or ''
                sheet.cell(row=row, column=16).value = record.permanent or ''
                sheet.cell(row=row, column=17).value = record.sonha_number_phone or ''
                sheet.cell(row=row, column=18).value = record.number_cccd or ''
                sheet.cell(row=row, column=19).value = date_cccd
                sheet.cell(row=row, column=20).value = record.place_of_issue or ''
                sheet.cell(row=row, column=21).value = record.tax_code or ''
                sheet.cell(row=row, column=22).value = 'Bậc nhân sự'
                sheet.cell(row=row, column=23).value = record.seniority_display
                sheet.cell(row=row, column=24).value = ''
                sheet.cell(row=row, column=25).value = record.culture_level or ''
                sheet.cell(row=row, column=26).value = ''
                sheet.cell(row=row, column=27).value = ''
                sheet.cell(row=row, column=28).value = record.contract_id.contract_type_id.name or ''
            # Báo cáo nhân sự nghỉ việc
            elif self.report.key == "nsnv":
                reception_date = record.reception_date.strftime('%d/%m/%Y') if record.reception_date else ""
                onboard = record.onboard.strftime('%d/%m/%Y') if record.reception_date else ""
                date_birthday = record.date_birthday.strftime('%d/%m/%Y') if record.reception_date else ""
                date_cccd = record.date_birthday.strftime('%d/%m/%Y') if record.reception_date else ""
                date_quit = record.date_quit.strftime('%d/%m/%Y') if record.date_quit else ""
                sheet.cell(row=row, column=1).value = stt
                sheet.cell(row=row, column=2).value = record.employee_code or ''
                sheet.cell(row=row, column=3).value = record.name or ''
                sheet.cell(row=row, column=4).value = date_birthday
                sheet.cell(row=row, column=5).value = record.get_gender_label() or ''
                sheet.cell(row=row, column=6).value = record.get_marital_status_label() or ''
                sheet.cell(row=row, column=7).value = record.nation or ''
                sheet.cell(row=row, column=8).value = record.get_religion_label() or ''
                sheet.cell(row=row, column=9).value = record.hometown or ''
                sheet.cell(row=row, column=10).value = record.permanent or ''
                sheet.cell(row=row, column=11).value = record.permanent or ''
                sheet.cell(row=row, column=12).value = str(record.sonha_number_phone) if record.sonha_number_phone else ''
                sheet.cell(row=row, column=13).value = record.number_cccd or ''
                sheet.cell(row=row, column=14).value = date_cccd
                sheet.cell(row=row, column=15).value = record.place_of_issue or ''
                sheet.cell(row=row, column=16).value = ''
                sheet.cell(row=row, column=17).value = ''
                sheet.cell(row=row, column=18).value = ''
                sheet.cell(row=row, column=19).value = record.contract_id.contract_type_id.name or ''
                sheet.cell(row=row, column=20).value = record.address_id or ''
                sheet.cell(row=row, column=21).value = record.department_id.name or ''
                sheet.cell(row=row, column=22).value = record.job_id.name or ''
                sheet.cell(row=row, column=23).value = onboard
                sheet.cell(row=row, column=24).value = reception_date
                sheet.cell(row=row, column=25).value = ''
                sheet.cell(row=row, column=26).value = date_quit or ''
                sheet.cell(row=row, column=27).value = date_quit or ''
                sheet.cell(row=row, column=28).value = record.reason_quit or ''
                sheet.cell(row=row, column=29).value = ''
            # Báo cáo nhân viên sinh nhật
            elif self.report.key == "nvsn":
                sheet.cell(row=row, column=1).value = stt
                sheet.cell(row=row, column=2).value = record.employee_code or ''
                sheet.cell(row=row, column=3).value = record.name or ''
                sheet.cell(row=row, column=4).value = str(record.date_birthday) or ''
                sheet.cell(row=row, column=5).value = record.job_id.name or ''
                sheet.cell(row=row, column=6).value = record.department_id.name or ''
                sheet.cell(row=row, column=7).value = ''
                sheet.cell(row=row, column=8).value = ''
                sheet.cell(row=row, column=9).value = ''
            # Báo cáo nhân sự theo hợp đồng
            elif self.report.key == "nsthd":
                contract_date_end = record.contract_id.date_end.strftime('%d/%m/%Y') if record.contract_id.date_end else ""
                if record.contract_id.contract_type_id and "cộng tác viên" in str(record.contract_id.contract_type_id.name).lower():
                    check_type = 'ctv'
                elif record.contract_id.contract_type_id and "thời vụ" in str(record.contract_id.contract_type_id.name).lower():
                    check_type = 'tvk'
                elif record.contract_id.contract_type_id and "thử việc" in str(record.contract_id.contract_type_id.name).lower():
                    check_type = 'tv'
                elif record.contract_id.contract_type_id and "xác định thời hạn" in str(record.contract_id.contract_type_id.name).lower():
                    check_type = 'cth'
                elif record.contract_id.contract_type_id and "không xác định thời hạn" in str(record.contract_id.contract_type_id.name).lower():
                    check_type = 'kth'
                else:
                    check_type = 'k'
                sheet.cell(row=row, column=1).value = stt
                sheet.cell(row=row, column=2).value = record.employee_code or ''
                sheet.cell(row=row, column=3).value = record.name or ''
                sheet.cell(row=row, column=4).value = record.address_id or ''
                sheet.cell(row=row, column=5).value = record.department_id.name or ''
                sheet.cell(row=row, column=6).value = record.job_id.name or ''
                sheet.cell(row=row, column=7).value = 'X' if check_type == 'ctv' else ''
                sheet.cell(row=row, column=8).value = 'X' if check_type == 'tvk' else ''
                sheet.cell(row=row, column=9).value = 'X' if check_type == 'tv' else ''
                sheet.cell(row=row, column=10).value = 'X' if check_type == 'cth' else ''
                sheet.cell(row=row, column=11).value = 'X' if check_type == 'kth' else ''
                sheet.cell(row=row, column=12).value = 'X' if check_type == 'k' and record.contract_id.contract_type_id else ''
                sheet.cell(row=row, column=13).value = ''
                sheet.cell(row=row, column=14).value = ''
                sheet.cell(row=row, column=15).value = ''
                sheet.cell(row=row, column=16).value = contract_date_end
                sheet.cell(row=row, column=17).value = ''
            if self.report.key != "ttc":
                row += 1
                sheet.insert_rows(row)
                stt += 1
        # Báo cáo thông tin chung
        if self.report.key == "ttc":
            list_department = list_record.mapped('department_id')
            for department in list_department:
                department_records = list_record.filtered(lambda x: x.department_id.id == department.id)
                count_male = len(department_records.filtered(lambda x: x.gender == 'male'))
                count_female = len(department_records.filtered(lambda x: x.gender == 'female'))
                count_thpt = len(department_records.filtered(lambda x: "trung học phổ thông" in str(x.culture_level).lower()))
                count_intermediate = len(department_records.filtered(lambda x: "trung cấp" in str(x.culture_level).lower()))
                count_college = len(department_records.filtered(lambda x: "cao đẳng" in str(x.culture_level).lower()))
                count_university = len(department_records.filtered(lambda x: "đại học" in str(x.culture_level).lower()))
                count_master = len(department_records.filtered(lambda x: "thạc sỹ" in str(x.culture_level).lower()))
                count_deputy_phd = len(department_records.filtered(lambda x: "phó tiến sỹ" in str(x.culture_level).lower()))
                count_phd = len(department_records.filtered(lambda x: "tiến sỹ" in str(x.culture_level).lower() and not "phó tiến sỹ" in str(x.culture_level).lower()))
                count_other_level = len(department_records.filtered(lambda x: str(x.culture_level) == ''))
                count_deputy_pro = len(department_records.filtered(lambda x: "phó giáo sư" in str(x.culture_level).lower()))
                count_pro = len(department_records.filtered(lambda x: "giáo sư" in str(x.culture_level).lower() and not "phó giáo sư" in str(x.culture_level).lower()))
                count_under_25 = len(department_records.filtered(lambda x: x.date_birthday and x.date_birthday.year > (now.year - 25)))
                count_25_30 = len(department_records.filtered(lambda x: x.date_birthday and x.date_birthday.year <= (now.year - 25) and x.date_birthday.year >= (now.year - 30)))
                count_31_40 = len(department_records.filtered(lambda x: x.date_birthday and x.date_birthday.year <= (now.year - 31) and x.date_birthday.year >= (now.year - 40)))
                count_41_50 = len(department_records.filtered(lambda x: x.date_birthday and x.date_birthday.year <= (now.year - 41) and x.date_birthday.year >= (now.year - 50)))
                count_above_50 = len(department_records.filtered(lambda x: x.date_birthday and x.date_birthday.year < (now.year - 50)))
                count_single = len(department_records.filtered(lambda x: x.marital_status == 'single'))
                count_married = len(department_records.filtered(lambda x: x.marital_status == 'married'))
                count_tern_contract = len(department_records.filtered(lambda x: "xác định thời hạn" in str(x.contract_id.contract_type_id.name).lower()))
                count_indefinite_contract = len(department_records.filtered(lambda x: "không xác định thời hạn" in str(x.contract_id.contract_type_id.name).lower()))
                count_probation_contract = len(department_records.filtered(lambda x: "thử việc" in str(x.contract_id.contract_type_id.name).lower()))
                count_temporary_contract = len(department_records.filtered(lambda x: "thời vụ" in str(x.contract_id.contract_type_id.name).lower()))
                count_collaborator_contract = len(department_records.filtered(lambda x: "cộng tác viên" in str(x.contract_id.contract_type_id.name).lower()))
                contract_type = ['xác định thời hạn', 'không xác định thời hạn', 'thử việc', 'thời vụ', 'cộng tác viên']
                other_contract = len(department_records.filtered(lambda x: all(contract not in str(x.contract_id.contract_type_id.name).lower() for contract in contract_type)))

                sheet.cell(row=row, column=1).value = stt
                sheet.cell(row=row, column=2).value = department.company_id.name or ''
                sheet.cell(row=row, column=3).value = department.name or ''
                sheet.cell(row=row, column=4).value = len(department_records)
                sheet.cell(row=row, column=5).value = count_male
                sheet.cell(row=row, column=6).value = count_female
                sheet.cell(row=row, column=7).value = count_thpt
                sheet.cell(row=row, column=8).value = count_intermediate
                sheet.cell(row=row, column=9).value = count_college
                sheet.cell(row=row, column=10).value = count_university
                sheet.cell(row=row, column=11).value = count_master
                sheet.cell(row=row, column=12).value = count_deputy_phd
                sheet.cell(row=row, column=13).value = count_phd
                sheet.cell(row=row, column=14).value = count_other_level
                sheet.cell(row=row, column=15).value = count_deputy_pro
                sheet.cell(row=row, column=16).value = count_pro
                sheet.cell(row=row, column=17).value = count_under_25
                sheet.cell(row=row, column=18).value = count_25_30
                sheet.cell(row=row, column=19).value = count_31_40
                sheet.cell(row=row, column=20).value = count_41_50
                sheet.cell(row=row, column=21).value = count_above_50
                sheet.cell(row=row, column=22).value = count_single
                sheet.cell(row=row, column=23).value = count_married
                sheet.cell(row=row, column=24).value = count_indefinite_contract
                sheet.cell(row=row, column=25).value = count_tern_contract
                sheet.cell(row=row, column=26).value = count_probation_contract
                sheet.cell(row=row, column=27).value = count_temporary_contract
                sheet.cell(row=row, column=28).value = count_collaborator_contract
                sheet.cell(row=row, column=29).value = other_contract
                sheet.cell(row=row, column=30).value = ''

                row += 1
                stt += 1

            # Lưu lại file kết quả
        max_lengths = defaultdict(int)
        for row in sheet.iter_rows(min_row=row_min, max_row=row, min_col=1, max_col=sheet.max_column):
            for cell in row:
                cell.border = thin_border
                cell.alignment = center_alignment
                if cell.value:
                    length = len(str(cell.value))
                    if length > max_lengths[cell.column]:
                        max_lengths[cell.column] = length

                # Cập nhật chiều rộng sau khi đã tính xong
        for col_idx, max_length in max_lengths.items():
            col_letter = get_column_letter(col_idx)
            sheet.column_dimensions[col_letter].width = max_length + 2
        for row in sheet.iter_rows(min_row=1, max_row=sheet.max_row, min_col=1, max_col=sheet.max_column):
            for cell in row:
                if isinstance(cell.value, str) and '[start_date]' in cell.value:
                    cell.value = cell.value.replace('[start_date]', start_date)
                if isinstance(cell.value, str) and '[end_date]' in cell.value:
                    cell.value = cell.value.replace('[end_date]', end_date)
                if isinstance(cell.value, str) and '[report_date]' in cell.value:
                    cell.value = cell.value.replace('[report_date]', str(report_date))
                    cell.value = cell.value.replace('[report_month]', str(report_month))
                    cell.value = cell.value.replace('[report_year]', str(report_year))
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
