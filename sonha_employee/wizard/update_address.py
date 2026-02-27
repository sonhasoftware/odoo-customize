from odoo import models, fields, api
import base64
import io
import pandas as pd


class UpdateAddress(models.TransientModel):
    _name = 'update.address'
    _description = 'Update Address'

    file = fields.Binary(string='Excel File', required=True)

    def import_employees(self):
        # Đọc file Excel
        if self.file:
            file_data = base64.b64decode(self.file)

            # Đọc file Excel
            df = pd.read_excel(
                io.BytesIO(file_data)
            )

            for index, row in df.iterrows():
                if row['Mã nhân viên']:
                    employee = self.env['hr.employee'].sudo().search([('employee_code', '=', row['Mã nhân viên'])])
                    if employee:
                        employee.place_birthday = row['Nơi sinh']
                        employee.hometown = row['Quê quán']
                        employee.permanent_address = row['Địa chỉ thường trú']
            return {'type': 'ir.actions.act_window_close'}