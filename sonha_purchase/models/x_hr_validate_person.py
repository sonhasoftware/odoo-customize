from odoo import fields, models, _

class XHrValidatePerson(models.Model):
    _name = 'x.hr.validate.person'

    name = fields.Char(string="Vai trò")

    def sync_x_hr_validate_person_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT name FROM x_hr_validate_person"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            for r in data:
                records_to_create.append({
                    'name': r.get('name')
                })

        if records_to_create:
            self.sudo().create(records_to_create)