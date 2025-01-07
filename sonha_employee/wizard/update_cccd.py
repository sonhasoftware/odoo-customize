from odoo import models, fields, api
import base64
import io
import pandas as pd


class UpdateCCCD(models.TransientModel):
    _name = 'update.cccd'
    _description = 'Update CCCD'

    file = fields.Binary(string='Excel File', required=True)

    def import_employees(self):
        # Đọc file Excel
        if self.file:
            file_data = base64.b64decode(self.file)

            # Đọc file Excel và ép cột 'Số CCCD' thành chuỗi
            df = pd.read_excel(
                io.BytesIO(file_data),
                dtype={'Số CCCD': str}  # Ép cột 'Số CCCD' là chuỗi
            )

            for index, row in df.iterrows():
                if row['Mã nhân viên']:
                    employee = self.env['hr.employee'].sudo().search([('employee_code', '=', row['Mã nhân viên'])])
                if employee:
                    employee.number_cccd = row['Số CCCD']  # Gán trực tiếp mà không cần chuyển đổi
            return {'type': 'ir.actions.act_window_close'}