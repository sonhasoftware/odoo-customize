from datetime import datetime, timedelta
import math

from odoo import models, fields, api
import base64
import io
import pandas as pd


class ImportAttendance(models.Model):
    _name = 'import.attendance'

    file = fields.Binary(string='Excel File', required=True)

    def import_employees(self):
        if self.file:
            file_data = base64.b64decode(self.file)
            df = pd.read_excel(io.BytesIO(file_data))

            for index, row in df.iterrows():
                if row['name']:
                    employee = self.env['hr.employee'].search([('device_id_num', '=', row['name'])], limit=1)
                parsed_time = datetime.strptime(str(row['date']), '%d/%m/%Y %H:%M:%S')
                if employee and parsed_time:
                    self.env['master.data.attendance'].sudo().create({
                        'employee_id': employee.id,
                        'attendance_time': parsed_time - timedelta(hours=7),
                    })
        return {'type': 'ir.actions.act_window_close'}

