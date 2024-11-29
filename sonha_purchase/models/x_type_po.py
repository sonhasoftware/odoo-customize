from odoo import models, fields, _

class XTypePO(models.Model):
    _name = 'x.type.po'

    name = fields.Char(string="Loại đơn mua")
    x_supply = fields.Boolean(string="Ban cung ứng mua hộ")

    def sync_x_type_po_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT name,x_supply FROM x_type_po"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            for r in data:
                records_to_create.append({
                    'name': r.get('name'),
                    'x_supply': r.get('x_supply')
                })

        if records_to_create:
            self.sudo().create(records_to_create)