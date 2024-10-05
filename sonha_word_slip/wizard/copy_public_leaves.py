from odoo import api, models, fields
import datetime


class CopyPublicLeaves(models.TransientModel):
    _name = 'copy.public.leaves'

    year = fields.Integer(string="Năm")

    def action_confirm(self):
        ids = self._context.get('active_ids')
        list_holiday = self.env['resource.calendar.leaves'].sudo().search([('id', 'in', ids)])
        for holiday in list_holiday:
            if holiday.name.endswith(')') and '(' in holiday.name and holiday.name[holiday.name.rfind('(') + 1: holiday.name.rfind('(') + 5].isdigit():
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