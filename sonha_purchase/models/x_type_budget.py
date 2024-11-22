from odoo import models, fields, _

class XTypeBudget(models.Model):
    _name = "x.type.budget"

    name = fields.Char(string="Loại ngân sách", stored=True)


    def sync_x_type_budget_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT id,name,create_uid,create_date,write_uid,write_date FROM x_type_budget"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            for r in data:
                records_to_create.append({
                    'name': r.get('name')
                })

        if records_to_create:
            self.sudo().create(records_to_create)
