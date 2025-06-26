from odoo import api, fields, models


class PlanCollaborate(models.Model):
    _name = 'plan.collaborate'

    code = fields.Char("Mã đơn", compute="get_code")
    type_collaborate = fields.Selection([('in', "Trong nước"),
                                         ('out', "Nước ngoài")],
                            string="Loại công tác",)
    total_price = fields.Float("Tổng chi phí(Dự trù)", compute="get_total_price")

    # giay di cong tac

    date = fields.Date("Ngày")
    employee_id = fields.Many2one('hr.employee', string="Họ và tên", compute="get_employee_info")
    department_id = fields.Many2one(related='employee_id.department_id', string="Đơn vị công tác")
    business = fields.Char("Được cử đi công tác tại:")
    gender = fields.Selection([('male', "Nam"),
                               ('female', "Nữ")],
                              string="Giới tính", compute="get_employee_info")
    from_date = fields.Date("Từ ngày", compute="get_date_business")
    to_date = fields.Date("Đến ngày", compute="get_date_business")

    car = fields.Boolean("Công ty cấp xe và lái xe")
    self_drive = fields.Boolean("Công ty cấp xe, tự lái xe")
    drive = fields.Boolean("Công ty cấp lái xe")
    sufficient = fields.Boolean("Tự túc")

    # end
    general_information = fields.One2many('general.information', 'plan_id', string="Thông tin chung")

    plan_detail = fields.One2many('plan.detail', 'plan_id', string="Kế hoạch công tác chi tiết")

    cost_coverage = fields.One2many('cost.coverage', 'plan_id', string="Chi phí được đài thọ")

    cost_estimated = fields.One2many('cost.estimated', 'plan_id', string="Chi phí dự kiến")

    def get_code(self):
        for r in self:
            if r.id:
                r.code = "BM.01 - Cong tac " + str(r.id)
            else:
                r.code = "BM.01 - Cong tac "

    @api.depends('cost_estimated')
    def get_total_price(self):
        for r in self:
            r.total_price = 0
            if r.cost_estimated:
                for price in r.cost_estimated:
                    r.total_price += price.price_vnd

    @api.depends('create_uid')
    def get_employee_info(self):
        for r in self:
            if r.create_uid:
                employee_id = self.env['hr.employee'].sudo().search([('user_id', '=', r.create_uid.id)])
                r.employee_id = employee_id.id if employee_id else None
                r.gender = employee_id.gender if employee_id.gender else None

    @api.depends('plan_detail')
    def get_date_business(self):
        for r in self:
            record_date = self.env['plan.detail'].sudo().search([('plan_id', '=', r.id)], order='time DESC')
            r.from_date = record_date[-1].time if record_date and record_date[-1].time else None
            r.to_date = record_date[0].time if record_date and record_date[0].time else None
