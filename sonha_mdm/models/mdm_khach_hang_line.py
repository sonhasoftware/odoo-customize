from odoo import fields, models


class MDMKhachHangLine(models.Model):
    _name = 'mdm.khach.hang.line'
    _description = 'Bảng con MDM khách hàng'

    khach_hang_id = fields.Many2one('mdm.khach.hang', string='Khách hàng', required=True, ondelete='cascade')
    ma_mdm = fields.Char(string='Mã MDM')
    ma_dv = fields.Char(string='Mã đơn vị')
    dvcs = fields.Many2one('res.company', string='ĐVCS')
