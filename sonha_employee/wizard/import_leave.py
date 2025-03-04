from odoo import models, fields, api
import base64
import io
import pandas as pd


class ImportLeave(models.TransientModel):
    _name = 'import.leave'
    _description = 'Import Leave'

    file = fields.Binary(string='Excel File', required=True)

    def import_employees(self):
        # Đọc file Excel
        if self.file:
            file_data = base64.b64decode(self.file)
            df = pd.read_excel(io.BytesIO(file_data))

            for index, row in df.iterrows():
                if row['Mã nhân viên']:
                    employee = self.env['hr.employee'].sudo().search([('employee_code', '=', row['Mã nhân viên'])])
                if employee:
                    employee.old_leave_balance = row['Phép tồn']
                    employee.new_leave_balance = row['Phép hiện tại']
            return {'type': 'ir.actions.act_window_close'}