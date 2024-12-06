from odoo import models, fields, _


class UomCategory(models.Model):
    _name = "uom.category.custom"

    name = fields.Char(string="Unit of Measure Category")

    def sync_uom_category_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT id,name FROM uom_category"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'name': r.get('name'),
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))