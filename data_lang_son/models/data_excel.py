from odoo import models, fields, api
import base64
import io
import pandas as pd


class DataExcel(models.Model):
    _name = 'data.excel'

    file = fields.Binary(string='File')
    file_name = fields.Char(string="Tên file")

    @api.onchange('file')
    def _onchange_file_data(self):
        if self.file and self.file_name:
            self.display_name = self.file_name

    def action_confirm(self):
        data = base64.b64decode(self.file)
        excel_file = io.BytesIO(data)
        df = pd.read_excel(excel_file, engine='openpyxl', dtype=str)  # .xlsx

        model = self.env['excel.data.lang.son']

        for _, row in df.iterrows():
            values = {field: str(row.get(field, '')).strip() if not pd.isna(row.get(field)) else ''
                      for field in df.columns}
            model.sudo().create(values)

    def cron_job_data_excel(self):
        self.with_delay().get_data_excel()

    def get_data_excel(self):
        list_excel = self.sudo().search([])
        for r in list_excel:
            data = base64.b64decode(r.file)
            excel_file = io.BytesIO(data)
            df = pd.read_excel(excel_file, engine='openpyxl', dtype=str)  # .xlsx

            model = self.env['excel.data.lang.son']

            for _, row in df.iterrows():
                values = {field: str(row.get(field, '')).strip() if not pd.isna(row.get(field)) else ''
                          for field in df.columns}
                model.sudo().create(values)
