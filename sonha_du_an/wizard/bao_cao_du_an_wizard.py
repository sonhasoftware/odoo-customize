from odoo import _, fields, models


class BaoCaoDuAnWizard(models.TransientModel):
    _name = 'sonha.du.an.bao.cao.wizard'
    _description = 'Tạo báo cáo dự án'

    tu_ngay = fields.Date(string='Từ ngày', required=True)
    den_ngay = fields.Date(string='Đến ngày', required=True)
    du_an_cha_id = fields.Many2one(
        'project.project', string='Dự án cha')

    def action_generate_report(self):
        self.ensure_one()
        report_args = [self.tu_ngay, self.den_ngay]
        if self.du_an_cha_id:
            report_args.append(self.du_an_cha_id.id)
        reports = self.env['sonha.du.an.bao.cao'].generate_from_function(*report_args)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Báo cáo dự án'),
            'res_model': 'sonha.du.an.bao.cao',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', reports.ids)],
        }
