from odoo import models, fields,_

class XProductLevel(models.Model):
    _name = 'x.product.level'

    x_level_number = fields.Integer(string="Cấp độ")

    def sync_x_product_level_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT id,x_level_number FROM x_product_level"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'x_level_number': r.get('x_level_number'),
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))