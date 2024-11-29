from odoo import models, fields, _


class UomCategory(models.Model):
    _name = "uom.category.custom"

    name = fields.Char(string="Unit of Measure Category")

    def sync_uom_category_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT name FROM uom_category"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            for r in data:
                records_to_create.append({
                    'name': r.get('name'),
                })

        if records_to_create:
            self.sudo().create(records_to_create)