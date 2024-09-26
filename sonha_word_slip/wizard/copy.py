from odoo import api, models, fields
import datetime


class Copy(models.TransientModel):
    _name = 'copy'

    year = fields.Integer(string="Năm")

    def action_confirm(self):
        list_holiday = self.env['resource.calendar.leaves'].sudo().search([])
        for holiday in list_holiday:
            if holiday.name.endswith(')') and '(' in holiday.name:
                base_name = holiday.name[:holiday.name.rfind('(')]
            else:
                base_name = holiday.name
            cop_name = base_name + " (" + str(self.year) + ")"
            start_time = holiday.date_from.replace(year=self.year)
            end_time = holiday.date_to.replace(year=self.year)
            vals = {
                'name': cop_name,
                'date_from': start_time,
                'date_to': end_time,
                'calendar_id': holiday.calendar_id.id,
            }
            duplicate_holidays = self.env['resource.calendar.leaves'].sudo().search([('date_from', '=', start_time),
                                                                                     ('date_to', '=', end_time)])
            if not duplicate_holidays:
                self.env['resource.calendar.leaves'].sudo().create(vals)