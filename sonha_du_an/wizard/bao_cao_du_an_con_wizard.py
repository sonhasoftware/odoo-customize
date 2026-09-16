from odoo import _, fields, models
from datetime import date


class BaoCaoDuAnConWizard(models.TransientModel):
    _name = 'sonha.du.an.con.bao.cao.wizard'
    _description = 'Tạo báo cáo dự án'

    tu_ngay = fields.Date(string='Từ ngày', required=True, default=lambda self: date.today().replace(month=1, day=1))
    den_ngay = fields.Date(string='Đến ngày', required=True, default=fields.Date.today)
    du_an_cha_id = fields.Many2one(
        'project.project', string='Dự án cha')

    def action_generate_report(self):
        self.ensure_one()
        report_model = self.env['sonha.du.an.bao.cao.con']

        # The report table is a generated snapshot.  Remove the previous
        # snapshot before running the database function so the result shown to
        # the user is always current and never mixed with older data.
        report_model.search([]).unlink()
        report_model.generate_from_function(
            self.tu_ngay,
            self.den_ngay,
            self.du_an_cha_id.id,
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _('Báo cáo dự án'),
            'res_model': 'sonha.du.an.bao.cao.con',
            'view_mode': 'tree,form',
            'context': {'search_default_group_by_parent': 1},
        }
