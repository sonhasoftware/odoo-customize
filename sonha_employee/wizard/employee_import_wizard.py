from datetime import datetime
import math

from odoo import models, fields, api
import base64
import io
import pandas as pd


class EmployeeImportWizard(models.TransientModel):
    _name = 'employee.import.wizard'
    _description = 'Import Employee Wizard'

    file = fields.Binary(string='Excel File', required=True)

    def import_employees(self):
        # Đọc file Excel
        if self.file:
            file_data = base64.b64decode(self.file)
            df = pd.read_excel(io.BytesIO(file_data))

            for index, row in df.iterrows():
                if row['Phòng ban']:
                    department_id = self.env['hr.department'].search([('name', '=', row['Phòng ban'])], limit=1)
                if row['Chức vụ']:
                    job_id = self.env['hr.job'].search([('name', '=', row['Chức vụ'])], limit=1)
                    if not job_id:
                        job = self.env['hr.job'].sudo().create({'name': row['Chức vụ']})
                if row['Công ty']:
                    company_id = self.env['res.company'].search([('name', '=', row['Công ty'])], limit=1)
                    if not company_id:
                        company = self.env['res.company'].sudo().create({'name': row['Công ty']})
                if row['giới tính'] == "Nữ":
                    gender = 'female'
                elif row['giới tính'] == "Nam":
                    gender = 'male'
                else:
                    gender = 'other'
                if row['Tình trạng hôn nhân'] == "Độc thân":
                    marital_status = 'single'
                else:
                    marital_status = 'married'

                if row['Tôn giáo'] == "Có":
                    religion = 'yes'
                else:
                    religion = 'no'

                if isinstance(row['Ngày cấp'], float) and math.isnan(row['Ngày cấp']):
                    date_cccd = None
                else:
                    date_cccd = datetime.strptime(str(row['Ngày cấp']), "%d/%m/%Y").strftime('%Y-%m-%d')

                if isinstance(row['Ngày tiếp nhận'], float) and math.isnan(row['Ngày tiếp nhận']):
                    reception_date = None
                else:
                    reception_date = datetime.strptime(str(row['Ngày tiếp nhận']), "%d/%m/%Y").strftime('%Y-%m-%d')

                if isinstance(row['Ngày vào công ty'], float) and math.isnan(row['Ngày vào công ty']):
                    onboard = None
                else:
                    onboard = datetime.strptime(str(row['Ngày vào công ty']), "%d/%m/%Y").strftime('%Y-%m-%d')

                if isinstance(row['Ngày sinh'], float) and math.isnan(row['Ngày sinh']):
                    date_birthday = None
                else:
                    date_birthday = datetime.strptime(str(row['Ngày sinh']), "%d/%m/%Y").strftime('%Y-%m-%d')

                self.env['hr.employee'].sudo().create({
                    'name': row['Họ tên'] or '',
                    'mobile_phone': row['Di động'] or '',
                    'work_email': row['email'] or '',
                    'department_id': department_id.id if department_id else None,
                    'job_id': job_id.id if job_id else job.id,
                    'date_birthday': date_birthday,
                    'gender': gender or '',
                    'marital_status': marital_status or '',
                    'nation': row['Dân tộc'] or '',
                    'religion': religion or '',
                    'hometown': row['Quê quán'] or '',
                    'permanent_address': row['Địa chỉ thường trú'] or '',
                    'number_cccd': row['Số CCCD'] or '',
                    'date_cccd': date_cccd,
                    'place_of_issue': row['Nơi cấp'] or '',
                    'employee_code': row['Mã nhân viên'] or '',
                    'device_id_num': row['Mã chấm công'] or '',
                    'onboard': onboard,
                    'reception_date': reception_date,
                    'tax_code': row['MST'] or '',
                    'company_id': company_id.id if company_id else company.id
                })

        return {'type': 'ir.actions.act_window_close'}
