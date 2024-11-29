from odoo import models, fields,_

class XProductLevel(models.Model):
    _name = 'x.product.level'

    x_level_number = fields.Integer(string="Cấp độ")

    def sync_x_product_level_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT x_level_number FROM x_product_level"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            for r in data:
                records_to_create.append({
                    'x_level_number': r.get('x_level_number'),
                })

        if records_to_create:
            self.sudo().create(records_to_create)