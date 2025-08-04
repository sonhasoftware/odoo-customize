from odoo import models, fields, api
import base64
import io
import pandas as pd


class ImportManagerWizard(models.TransientModel):
    _name = 'import.manager.wizard'
    _description = 'Import Manager Wizard'

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
                    employee.level = row['Cấp bậc']
            return {'type': 'ir.actions.act_window_close'}