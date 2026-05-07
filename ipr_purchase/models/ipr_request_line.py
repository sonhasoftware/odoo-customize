from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class IprRequestLine(models.Model):
    _name = 'ipr.request.line'
    _description = 'Internal Purchase Request Line'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'ipr.request',
        string='Phiếu yêu cầu',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='STT', default=10)

    product_id = fields.Many2one(
        'product.product',
        string='Sản phẩm',
        required=True,
        domain=[('purchase_ok', '=', True)],
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string='Đơn vị',
        related='product_id.uom_po_id',
        readonly=True,
    )
    description = fields.Char(
        string='Mô tả',
        compute='_compute_description',
        store=True,
        readonly=False,
    )
    quantity = fields.Float(
        string='Số lượng',
        default=1.0,
        digits='Product Unit of Measure',
        required=True,
    )
    price_unit = fields.Float(
        string='Đơn giá',
        digits='Product Price',
    )
    subtotal = fields.Float(
        string='Thành tiền',
        compute='_compute_subtotal',
        store=True,
        digits=(16, 2),
    )
    company_id = fields.Many2one(
        related='request_id.company_id',
        store=True,
    )

    # ─── Compute ─────────────────────────────────────────────────────────────
    @api.depends('product_id')
    def _compute_description(self):
        for line in self:
            line.description = line.product_id.name if line.product_id else ''

    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    # ─── Onchange ─────────────────────────────────────────────────────────────
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Khi chọn product → tự động fill đơn giá và mô tả."""
        if self.product_id:
            self.price_unit = self.product_id.standard_price or self.product_id.list_price
            self.description = self.product_id.name

    # ─── Constraints ─────────────────────────────────────────────────────────
    @api.constrains('quantity')
    def _check_quantity_positive(self):
        for line in self:
            if line.quantity <= 0:
                raise ValidationError(_(
                    'Số lượng của sản phẩm "%s" phải lớn hơn 0.'
                ) % line.product_id.name)

    @api.constrains('price_unit')
    def _check_price_non_negative(self):
        for line in self:
            if line.price_unit < 0:
                raise ValidationError(_(
                    'Đơn giá của sản phẩm "%s" không được âm.'
                ) % line.product_id.name)
