from odoo import models, fields,_

class XPOTypeConfig(models.Model):
    _name = 'x.po.type.config'

    name = fields.Char(string="Loại PO")
    x_cancel_validate = fields.Boolean(string="Cấp duyệt cuối xác nhạn hủy")
    x_time_approve_po = fields.Float(string="Thời gian quy định duyệt PO")

    def sync_x_po_type_config_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = """
            SELECT 
                name,
                x_cancel_validate,
                x_time_approve_po 
            FROM 
                x_po_type_config
        """

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            for r in data:
                records_to_create.append({
                    'name': r.get('name'),
                    'x_cancel_validate': r.get('x_cancel_validate'),
                    'x_time_approve_po': r.get('x_time_approve_po'),
                })

        if records_to_create:
            self.sudo().create(records_to_create)