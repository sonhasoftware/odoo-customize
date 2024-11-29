from odoo import fields,models,_

class XPRTypeConfig(models.Model):
    _name = 'x.pr.type.config'

    name = fields.Char(string="Loại PR")

    def sync_x_pr_type_config_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT name FROM x_pr_type_config"

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