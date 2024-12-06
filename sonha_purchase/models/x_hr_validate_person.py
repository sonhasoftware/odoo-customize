from odoo import fields, models, _

class XHrValidatePerson(models.Model):
    _name = 'x.hr.validate.person'

    name = fields.Char(string="Vai trò")

    def sync_x_hr_validate_person_data(self):
        connector = self.env['external.db.connector'].sudo()
        query = "SELECT id,name FROM x_hr_validate_person"

        data = connector.execute_query(query)
        records_to_create = []

        if data:
            self.search([]).sudo().unlink()
            self.with_context(active_test=False).sudo().search([]).unlink()
            for r in data:
                records_to_create.append({
                    'name': r.get('name')
                })

        if records_to_create:
            created_records = self.sudo().create(records_to_create)

            for record, r in zip(created_records, data):
                self.env.cr.execute("""
                            UPDATE {} 
                            SET id = %s 
                            WHERE id = %s
                        """.format(self._table), (r.get('id'), record.id))