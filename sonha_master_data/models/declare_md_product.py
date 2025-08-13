from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class DeclareMDProduct(models.Model):
    _name = 'declare.md.product'

    product_code = fields.Char("Mã vật tư")
    product_type = fields.Many2one('x.material.type', string="Loại vật tư")
    product_name = fields.Char("Tên vật tư", size=40)
    product_english_name = fields.Char("Tên vật tư tiếng anh", compute="get_product_name", store=True)
    product_long_name = fields.Char("Tên đầy đủ", size=128)
    status = fields.Selection([('draft', "Nháp"), ('waiting', "Chờ duyệt"), ('done', "Đã duyệt")],
                              string="Trạng thái", default='draft')
    basic_data = fields.One2many('basic.mat.data', 'product_code_id', string="Thông tin cơ bản")
    alternative_uom = fields.One2many('alternative.uom', 'product_code_id', string="Đơn vị thay thế")
    plant_data = fields.One2many('plant.data', 'product_code_id', string="Thông tin plant")
    sale_data = fields.One2many('sales.data', 'product_code_id', string="Thông tin bán hàng")
    have_alt_uom = fields.Boolean("Đơn vị tính khác")
    is_z100 = fields.Boolean("Là thành phẩm sản xuất tại một đơn vị trong tập đoàn")
    is_z101 = fields.Boolean("Là bán thành phẩm sản xuất tại một đơn vị trong tập đoàn")
    is_z102 = fields.Boolean("Là thành phẩm sản xuất tại một đơn vị trong tập đoàn loại 2")
    compute_alt_uom = fields.Boolean(compute="compute_alt_uom_check", store=True)

    next_approve_employee = fields.Many2many('hr.employee', string="Người duyệt")
    employee_id = fields.Many2one('hr.employee', string="Người tạo", default=lambda self: self.get_create_employee())
    md_approve_display = fields.One2many('md.approve.display', 'md_product', string="Quy trình duyệt")
    company_id = fields.Many2one('res.company', string="Đơn vị", required=True)

    def get_create_employee(self):
        employee = self.env['hr.employee'].sudo().search([('user_id', '=', self.env.uid)])
        if employee:
            return employee.id

    def get_approve_people(self, record, employee):
        admin = self.env['hr.employee'].sudo().search([('id', '=', 1)])
        approve_people = admin
        employee_id = self.env['hr.employee'].sudo().search([('id', '=', employee.id)])
        if record.method == 'role':
            if record.approve_role and record.approve_role.approve_employee:
                approve_people = record.approve_role.approve_employee
        elif record.method == 'assign':
            if record.employee_id:
                approve_people = record.employee_id
        elif record.method == 'parent':
            if employee_id.parent_id:
                approve_people = employee_id.parent_id
        else:
            if employee_id.department_id and employee_id.department_id.manager_id:
                approve_people = employee_id.department_id.manager_id
        return approve_people

    def get_approve_employee(self):
        for r in self:
            list_suggest = r.md_approve_display.filtered(lambda x: x.level == 'suggest' and x.status == 'waiting')
            if list_suggest and r.status == 'draft':
                next_approve_people = list_suggest.mapped('employee_id')
            else:
                list_approve = r.md_approve_display.filtered(lambda x: x.level not in ['suggest', 'examine', 'notice'] and x.status == 'waiting')
                list_approve = list_approve.sorted(key=lambda x: (x.sequence_step, x.id))
                next_approve_people = list_approve[0].employee_id
            return next_approve_people

    @api.depends('basic_data.malt_prdhier')
    def compute_alt_uom_check(self):
        for r in self:
            if r.basic_data.malt_prdhier.code in ['00210001000001', '00220001000001', '00230001000001']:
                r.compute_alt_uom = True
                r.have_alt_uom = True
            else:
                r.compute_alt_uom = False
                r.have_alt_uom = False

    @api.onchange('is_z100', 'is_z101', 'is_z102')
    def filter_product_type(self):
        for r in self:
            if r.is_z100:
                code = "Z100"
                r.is_z101 = False
                r.is_z102 = False
            if r.is_z101:
                code = "Z101"
                r.is_z100 = False
                r.is_z102 = False
            if r.is_z102:
                code = "Z102"
                r.is_z101 = False
                r.is_z100 = False
            if r.is_z100 or r.is_z101 or r.is_z102:
                product_type = self.env['x.material.type'].sudo().search([('x_code', '=', code)])
                r.product_type = product_type.id
            else:
                r.product_type = None

    def unlink(self):
        for r in self:
            self.env['basic.mat.data'].search([('product_code_id', '=', r.id)]).sudo().unlink()
            self.env['alternative.uom'].search([('product_code_id', '=', r.id)]).sudo().unlink()
            self.env['plant.data'].search([('product_code_id', '=', r.id)]).sudo().unlink()
            self.env['sales.data'].search([('product_code_id', '=', r.id)]).sudo().unlink()
        return super(DeclareMDProduct, self).unlink()

    def action_approve(self):
        for r in self:
            if r.status == 'waiting':
                if self.env.user.employee_ids in r.next_approve_employee or self.env.uid == 2:
                    list_approve = r.md_approve_display.filtered(lambda x: x.level not in ['examine', 'notice'] and x.status == 'waiting')
                    if len(list_approve) == 1:
                        list_approve[0].sudo().write({'status': 'done'})
                        r.status = 'done'
                        vals = {
                            'product_type': r.product_type.id,
                            'product_name': r.product_name,
                            'product_english_name': r.product_english_name,
                            'product_long_name': r.product_long_name,
                            'declare_product': r.id,
                        }
                        md_product = self.env['md.product'].sudo().create(vals)
                        basic_data = self.env['basic.mat.data'].sudo().search([('product_code_id', '=', r.id)])
                        if basic_data:
                            basic_data.sudo().write({'md_product_id': md_product.id})
                        alt_uom = self.env['alternative.uom'].sudo().search([('product_code_id', '=', r.id)])
                        if alt_uom:
                            alt_uom.sudo().write({'md_product_id': md_product.id})
                        plant_data = self.env['plant.data'].sudo().search([('product_code_id', '=', r.id)])
                        if plant_data:
                            plant_data.sudo().write({'md_product_id': md_product.id})
                        sale_data = self.env['sales.data'].sudo().search([('product_code_id', '=', r.id)])
                        if sale_data:
                            sale_data.sudo().write({'md_product_id': md_product.id})
                    else:
                        list_suggest = r.md_approve_display.filtered(lambda x: x.level == 'suggest' and x.status == 'waiting')
                        if list_suggest:
                            list_suggest.sudo().write({'status': 'done'})
                        else:
                            list_approve[0].sudo().write({'status': 'done'})
                        next_approve_people = r.get_approve_employee()
                        r.next_approve_employee = next_approve_people
                else:
                    raise ValidationError("Bạn không có quyền duyệt bước này!")
            else:
                raise ValidationError("Bạn không thể duyệt bản ghi này!")

    def action_sent(self):
        list_alt_uom = ['00210001000001', '00220001000001', '00230001000001']
        for r in self:
            if r.employee_id.user_id.id == self.env.uid or self.env.uid == 2:
                if r.have_alt_uom and not r.alternative_uom:
                    raise ValidationError("Cần khai báo đơn vị thay thế cho vật tư!")
                if r.basic_data.malt_prdhier.code in list_alt_uom and r.alternative_uom.alternative_unit.name != "Cây":
                    raise ValidationError("Đơn vị thay thế phải là Cây!")
                model_id = self.env['ir.model'].sudo().search([('model', '=', 'declare.md.product')], limit=1).id
                approve_rule = self.env['md.approve.rule'].sudo().search([('model_apply', '=', model_id),
                                                                          ('company_ids', 'in', r.company_id.id)])
                if approve_rule:
                    for record in approve_rule.step:
                        approve_emp = self.get_approve_people(record, r.employee_id)
                        val = {
                            'sequence_step': record.sequence_step,
                            'level': record.level,
                            'employee_id': approve_emp.id,
                            'md_product': r.id,
                        }
                        self.env['md.approve.display'].sudo().create(val)
                    approve_record = approve_rule.step.filtered(lambda x: x.level not in ['suggest', 'examine', 'notice'])
                    if not approve_record:
                        admin = self.env['hr.employee'].sudo().search([('id', '=', 1)])
                        val = {
                            'sequence_step': len(approve_rule.step) + 1,
                            'level': 'approve',
                            'employee_id': admin.id,
                            'md_product': r.id,
                        }
                        self.env['md.approve.display'].sudo().create(val)
                else:
                    admin = self.env['hr.employee'].sudo().search([('id', '=', 1)])
                    val = {
                        'sequence_step': 1,
                        'level': 'approve',
                        'employee_id': admin.id,
                        'md_product': r.id,
                    }
                    self.env['md.approve.display'].sudo().create(val)
                r.next_approve_employee = r.get_approve_employee()
                r.status = 'waiting'
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def to_draft_action(self):
        for r in self:
            if self.env.user.employee_ids in r.next_approve_employee or self.env.uid == 2:
                r.next_approve_employee = None
                r.status = 'draft'
                record = self.env['md.product'].sudo().search([('declare_product', '=', r.id)])
                if record:
                    record.sudo().unlink()
                self.env['md.approve.display'].sudo().search([('md_product', '=', r.id)]).unlink()
            else:
                raise ValidationError("Bạn không có quyền thực hiện hành động này!")

    def multi_approval(self):
        for r in self:
            r.action_approve()

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, access_rights_uid=None):
        new_domain = []
        for dm in domain:
            if isinstance(dm, (list, tuple)) and len(dm) == 3:
                field, operator, value = dm
                if value and isinstance(value, str) and '*' in value and operator == 'ilike':
                    temp = []
                    parts = value.split('*')
                    for part in parts:
                        if part.strip():
                            temp.append((field, 'ilike', part.strip()))
                    if temp:
                        new_domain += ['&'] * (len(temp) - 1)
                        new_domain += temp
                else:
                    new_domain.append(dm)
            else:
                new_domain.append(dm)
        domain = new_domain
        return super(DeclareMDProduct, self)._search(domain, offset, limit, order, access_rights_uid)

    line = fields.Boolean("Dòng sản phẩm", default=True, compute="compute_hide_show", store=True)
    stage = fields.Boolean("Công đoạn/Sản phẩm", default=True, compute="compute_hide_show", store=True)
    brand = fields.Boolean("Nhãn hiệu/Chủng loại", default=False, compute="compute_hide_show", store=True)
    model = fields.Boolean("Model", default=False, compute="compute_hide_show", store=True)
    style = fields.Boolean("Kiểu dáng", default=False, compute="compute_hide_show", store=True)
    capacity = fields.Boolean("Dung tích", default=False, compute="compute_hide_show", store=True)
    power = fields.Boolean("Công suất", default=False, compute="compute_hide_show", store=True)
    substance = fields.Boolean("Chất liệu", default=False, compute="compute_hide_show", store=True)
    surface = fields.Boolean("Kiểu bề mặt/Độ bóng", default=False, compute="compute_hide_show", store=True)
    diameter = fields.Boolean("Đường kính", default=False, compute="compute_hide_show", store=True)
    thickness = fields.Boolean("Độ dày", default=False, compute="compute_hide_show", store=True)
    size = fields.Boolean("Chiều dài, rộng, cao", default=False, compute="compute_hide_show", store=True)
    chemical = fields.Boolean("TP hóa học", default=False, compute="compute_hide_show", store=True)
    color = fields.Boolean("Màu sắc", default=False, compute="compute_hide_show", store=True)
    other = fields.Boolean("Khác", default=False, compute="compute_hide_show", store=True)
    tech_spec = fields.Boolean("Thông số kỹ thuật", default=False, compute="compute_hide_show", store=True)
    specific = fields.Boolean("Đặc thù/Mục đích", default=False, compute="compute_hide_show", store=True)
    country = fields.Boolean("Nước sản xuất", default=False, compute="compute_hide_show", store=True)

    product_line = fields.Many2one('product.line', string="Dòng sản phẩm",
                                   domain="[('material_type', 'in', product_type)]")
    product_stage = fields.Many2one('product.stage', string="Công đoạn/Sản phẩm",
                                    domain="[('product_line', '=', product_line)]")
    product_brand = fields.Many2one('product.brand', string="Nhãn hiệu/Chủng loại")
    product_model = fields.Many2one('product.model', string="Model")
    product_style = fields.Many2one('product.style', string="Kiểu dáng")
    product_capacity = fields.Many2one('product.capacity', string="Dung tích", domain="[('type', '=', 'capacity')]")
    product_power = fields.Many2one('product.capacity', string="Công suất", domain="[('type', '=', 'power')]")
    product_substance = fields.Many2one('product.substance', string="Chất liệu")
    product_surface = fields.Many2one('product.surface', string="Kiểu bề mặt")
    product_diameter = fields.Many2one('product.diameter', string="Đường kính")
    product_thickness = fields.Many2one('product.thickness', string="Độ dày")
    product_size = fields.Many2one('product.size', string="Chiều dài, rộng, cao")
    product_chemical = fields.Many2one('product.chemical', string="TP hóa học")
    product_color = fields.Many2one('product.color', string="Màu sắc")
    product_other = fields.Many2one('product.other', string="Khác")
    product_other_char = fields.Char("Khác")
    product_tech_spec = fields.Char("Thông số kỹ thuật")
    product_specific = fields.Char("Đặc thù/Mục đích")
    product_country = fields.Many2one('res.country', string="Nước sản xuất")

    @api.depends('product_line', 'product_stage', 'product_type.x_code')
    def compute_hide_show(self):
        for r in self:
            if r.product_type.x_code in ['Z500', 'Z205']:
                r.line = False
                r.stage = False
                r.brand = False
                r.model = False
                r.style = False
                r.capacity = False
                r.power = False
                r.substance = False
                r.surface = False
                r.diameter = False
                r.thickness = False
                r.size = False
                r.chemical = False
                r.color = False
                r.other = False
                r.tech_spec = False
                r.specific = False
                r.country = False
            elif r.product_type.x_code not in ['Z500', 'Z205']:
                r.line = True
                r.stage = True
                if r.product_type.x_code in ['Z100', 'Z101'] and r.product_line and r.product_stage or (r.product_type.x_code == "Z200" and r.product_line.is_main_material):
                    name_rule = self.env['product.name.rule'].sudo().search([('product_line', '=', r.product_line.id),
                                                                             ('product_stage', '=', r.product_stage.id)])
                    if name_rule:
                        r.brand = name_rule.brand
                        r.model = name_rule.model
                        r.style = name_rule.style
                        r.capacity = name_rule.capacity
                        r.power = name_rule.power
                        r.substance = name_rule.substance
                        r.surface = name_rule.surface
                        r.diameter = name_rule.diameter
                        r.thickness = name_rule.thickness
                        r.size = name_rule.size
                        r.chemical = name_rule.chemical
                        r.color = name_rule.color
                        r.other = name_rule.other
                        r.country = False
                        r.specific = False
                        r.tech_spec = False
                    else:
                        r.brand = False
                        r.model = False
                        r.style = False
                        r.capacity = False
                        r.power = False
                        r.substance = False
                        r.surface = False
                        r.diameter = False
                        r.thickness = False
                        r.size = False
                        r.chemical = False
                        r.color = False
                        r.other = False
                        r.country = False
                        r.specific = False
                        r.tech_spec = False
                elif r.product_type.x_code and r.product_type.x_code not in ['Z100', 'Z101', 'Z205', 'Z200'] or (r.product_line and r.product_type.x_code == "Z200" and not r.product_line.is_main_material):
                    r.stage = False
                    r.brand = True
                    r.model = True
                    r.tech_spec = True
                    r.color = True
                    r.country = True
                    r.specific = True
                    r.style = False
                    r.capacity = False
                    r.power = False
                    r.substance = False
                    r.surface = False
                    r.diameter = False
                    r.thickness = False
                    r.size = False
                    r.chemical = False
                    r.other = False
            elif not r.product_type.x_code or not r.product_line:
                r.brand = False
                r.model = False
                r.style = False
                r.capacity = False
                r.power = False
                r.substance = False
                r.surface = False
                r.diameter = False
                r.thickness = False
                r.size = False
                r.chemical = False
                r.color = False
                r.other = False
                r.country = False
                r.specific = False
                r.tech_spec = False

    @api.onchange('product_line', 'product_stage')
    def onchange_name_product(self):
        self.product_brand = None
        self.product_model = None
        self.product_style = None
        self.product_capacity = None
        self.product_power = None
        self.product_substance = None
        self.product_surface = None
        self.product_diameter = None
        self.product_thickness = None
        self.product_size = None
        self.product_chemical = None
        self.product_color = None
        self.product_other_char = None
        self.product_country = None
        self.product_tech_spec = None
        self.product_specific = None
        self.product_name = None
        self.product_english_name = None
        self.product_long_name = None

    @api.onchange('product_type')
    def onchange_product_type(self):
        self.product_line = None
        self.product_stage = None
        self.product_brand = None
        self.product_model = None
        self.product_style = None
        self.product_capacity = None
        self.product_power = None
        self.product_substance = None
        self.product_surface = None
        self.product_diameter = None
        self.product_thickness = None
        self.product_size = None
        self.product_chemical = None
        self.product_color = None
        self.product_other_char = None
        self.product_country = None
        self.product_tech_spec = None
        self.product_specific = None
        self.product_name = None
        self.product_english_name = None
        self.product_long_name = None

    @api.onchange('product_stage', 'product_brand', 'product_model',
                  'product_style', 'product_capacity', 'product_power', 'product_substance',
                  'product_surface', 'product_diameter', 'product_thickness', 'product_size',
                  'product_chemical', 'product_color', 'product_other_char', 'product_country',
                  'product_tech_spec', 'product_specific',)
    def get_product_name(self):
        for r in self:
            name = ""
            full_name = ""
            if r.product_line and r.product_type.x_code not in ['Z100', 'Z101'] and not r.product_line.is_main_material:
                name = name + str(r.product_line.name)
                full_name = full_name + str(r.product_line.name)
            if r.product_stage:
                name = name + str(r.product_stage.short_name)
                full_name = full_name + str(r.product_stage.full_name)
            if r.product_brand:
                name = name + " " + str(r.product_brand.short_name)
                full_name = full_name + " " + str(r.product_brand.full_name)
            if r.product_model:
                name = name + " " + str(r.product_model.name)
                full_name = full_name + " " + str(r.product_model.name)
            if r.product_tech_spec:
                name = name + " " + r.product_tech_spec
                full_name = full_name + " " + r.product_tech_spec
            if r.product_style:
                name = name + " " + str(r.product_style.short_name)
                full_name = full_name + " " + str(r.product_style.full_name)
            if r.product_capacity:
                name = name + " " + str(r.product_capacity.name)
                full_name = full_name + " " + str(r.product_capacity.name)
            if r.product_power:
                name = name + " " + str(r.product_power.name)
                full_name = full_name + " " + str(r.product_power.name)
            if r.product_substance:
                name = name + " " + str(r.product_substance.name)
                full_name = full_name + " " + str(r.product_substance.name)
            if r.product_surface:
                name = name + " " + str(r.product_surface.name)
                full_name = full_name + " " + str(r.product_surface.name)
            if r.product_diameter:
                name = name + " " + str(r.product_diameter.name)
                full_name = full_name + " " + str(r.product_diameter.name)
            if r.product_thickness:
                name = name + " " + str(r.product_thickness.name)
                full_name = full_name + " " + str(r.product_thickness.name)
            if r.product_size:
                name = name + " " + str(r.product_size.name)
                full_name = full_name + " " + str(r.product_size.name)
            if r.product_chemical:
                name = name + " " + str(r.product_chemical.name)
                full_name = full_name + " " + str(r.product_chemical.name)
            if r.product_color:
                name = name + " " + str(r.product_color.name)
                full_name = full_name + " " + str(r.product_color.name)
            if r.product_other:
                name = name + " " + r.product_other
                full_name = full_name + " " + r.product_other
            if r.product_country:
                name = name + " " + str(r.product_country.name)
                full_name = full_name + " " + str(r.product_country.name)
            if r.product_specific:
                name = name + " " + r.product_specific
                full_name = full_name + " " + r.product_specific
            r.product_english_name = name
            r.product_long_name = full_name
            r.product_name = name




