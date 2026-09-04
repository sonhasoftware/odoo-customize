import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BaoCaoDuAn(models.Model):

    _name = 'sonha.du.an.bao.cao'
    _description = 'Báo cáo dự án'
    _table = 'bao_cao'

    _order = """
        ngay_tao_bao_cao desc,
        parent_group_id,
        child_group_id,
        in_dam,
        stt,
        id
    """

    name = fields.Char(
        string='Tên',
        required=True,
        readonly=True
    )

    tu_ngay = fields.Date(
        string='Từ ngày',
        required=True,
        readonly=True
    )

    den_ngay = fields.Date(
        string='Đến ngày',
        required=True,
        readonly=True
    )

    du_an_cha_id = fields.Many2one(
        'project.project',
        string='Dự án cha',
        readonly=True,
        ondelete='restrict',
        index=True,
    )

    stt = fields.Integer(
        string='STT',
        readonly=True
    )

    noi_dung_cv_con = fields.Char(
        string='Nội dung công việc con',
        readonly=True
    )

    ngay_bat_dau = fields.Date(
        string='Ngày bắt đầu',
        readonly=True
    )

    ngay_ket_thuc = fields.Date(
        string='Ngày kết thúc',
        readonly=True
    )

    ten_trang_thai = fields.Text(
        string='Tên trạng thái',
        readonly=True
    )

    tinh_trang_han = fields.Text(
        string='Tình trạng hạn',
        readonly=True
    )

    pt_cv = fields.Float(
        string='% công việc',
        readonly=True
    )

    ns_lam = fields.Text(
        string='Nhân sự làm',
        readonly=True
    )

    in_dam = fields.Integer(
        string='In đậm',
        readonly=True
    )

    du_an_con_id = fields.Integer(
        string='Dự án con ID',
        readonly=True
    )

    # ==============================
    # FIELD PHỤC VỤ GROUP BY
    # ==============================

    parent_group_id = fields.Integer(
        string='Nhóm dự án cha',
        readonly=True,
        index=True,
    )

    child_group_id = fields.Integer(
        string='Nhóm dự án con',
        readonly=True,
        index=True,
    )

    du_lieu = fields.Text(
        string='Dữ liệu báo cáo',
        required=True,
        readonly=True
    )

    ngay_tao_bao_cao = fields.Datetime(
        string='Ngày tạo báo cáo',
        required=True,
        readonly=True,
        default=fields.Datetime.now,
    )

    # ==========================================
    # TẠO DỮ LIỆU TỪ POSTGRESQL FUNCTION
    # ==========================================

    @api.model
    def generate_from_function(
        self,
        tu_ngay,
        den_ngay,
        du_an_cha_id=False
    ):

        if not tu_ngay or not den_ngay:
            raise ValidationError(
                _("Bạn phải nhập từ ngày và đến ngày.")
            )

        start_date = fields.Date.to_date(tu_ngay)
        end_date = fields.Date.to_date(den_ngay)

        if start_date > end_date:
            raise ValidationError(
                _("Từ ngày không được lớn hơn đến ngày.")
            )

        # ==========================================
        # GỌI POSTGRESQL FUNCTION
        # ==========================================

        query_params = (
            start_date.strftime('%d/%m/%Y'),
            end_date.strftime('%d/%m/%Y'),
            du_an_cha_id or None,
        )

        query = """
            SELECT *
            FROM public.fn_bao_cao_du_an(%s, %s, %s)
        """

        self.env.cr.execute(
            query,
            query_params
        )

        rows = self.env.cr.dictfetchall()

        generated_at = fields.Datetime.now()

        project_name = (
            self.env['project.project']
            .browse(du_an_cha_id)
            .display_name
            if du_an_cha_id
            else _("Tất cả dự án")
        )

        # ==========================================
        # TẠO DỮ LIỆU CƠ BẢN
        # ==========================================

        values = [
            {
                # ``name`` is used as the label when the report is grouped
                # by ``parent_id``.  Use the report content rather than an
                # internal row number so the group header identifies the
                # parent/child project or task it contains.
                'name': row.get('noi_dung_cv_con') or _(
                    '%(project)s - dòng %(line)s'
                ) % {
                    'project': project_name,
                    'line': index,
                },

                'tu_ngay': tu_ngay,
                'den_ngay': den_ngay,

                'du_an_cha_id': du_an_cha_id,

                'stt': index,

                'noi_dung_cv_con': row.get(
                    'noi_dung_cv_con'
                ),

                'ngay_bat_dau': row.get(
                    'ngay_bat_dau'
                ),

                'ngay_ket_thuc': row.get(
                    'ngay_ket_thuc'
                ),

                'ten_trang_thai': row.get(
                    'ten_trang_thai'
                ),

                'tinh_trang_han': row.get(
                    'tinh_trang_han'
                ),

                'pt_cv': row.get(
                    'pt_cv'
                ),

                'ns_lam': row.get(
                    'ns_lam'
                ),

                'in_dam': row.get(
                    'in_dam'
                ),

                'du_an_con_id': row.get(
                    'du_an_con_id'
                ),

                'du_lieu': json.dumps(
                    row,
                    ensure_ascii=False,
                    default=str,
                    sort_keys=True
                ),

                'ngay_tao_bao_cao': generated_at,
            }

            for index, row in enumerate(
                rows,
                start=1
            )
        ]

        # ==========================================
        # TẠO QUAN HỆ GROUP
        # ==========================================

        created_records = self.browse()

        # ID nhóm dự án cha hiện tại
        current_parent_group_id = False

        # Mapping:
        #
        # du_an_con_id
        #       ↓
        # ID RECORD CỦA DỰ ÁN CON
        #
        child_project_map = {}

        for value in values:

            level = value.get('in_dam')

            # ======================================
            # DỰ ÁN CHA
            # in_dam = 1
            # ======================================

            if level == 1:

                current_parent_group_id = (
                    value.get('du_an_con_id')
                )

                value['parent_group_id'] = (
                    current_parent_group_id
                )

                value['child_group_id'] = 0

                record = self.create(value)

                created_records |= record


            # ======================================
            # DỰ ÁN CON
            # in_dam = 2
            # ======================================

            elif level == 2:

                value['parent_group_id'] = (
                    current_parent_group_id
                )

                # Tạo record trước
                record = self.create(value)

                # ID record vừa tạo
                child_record_id = record.id

                value_child_id = value.get(
                    'du_an_con_id'
                )

                # Cập nhật child group
                record.write({
                    'child_group_id': child_record_id
                })

                # Lưu mapping
                #
                # du_an_con_id hiện tại
                # -> ID record Odoo
                #
                child_project_map[
                    child_record_id
                ] = {
                    'parent_group_id':
                        current_parent_group_id,

                    'child_group_id':
                        child_record_id,
                }

                created_records |= record


            # ======================================
            # NHIỆM VỤ
            # in_dam = 99
            # ======================================

            elif level == 99:

                child_project_id = value.get(
                    'du_an_con_id'
                )

                # Parent group
                value['parent_group_id'] = (
                    current_parent_group_id
                )

                # Child group
                value['child_group_id'] = (
                    child_project_id
                )

                record = self.create(value)

                created_records |= record


            # ======================================
            # DỮ LIỆU KHÁC
            # ======================================

            else:

                value['parent_group_id'] = False

                value['child_group_id'] = False

                record = self.create(value)

                created_records |= record


        return created_records


    def action_open_generate_wizard(self):

        return {
            'type': 'ir.actions.act_window',

            'name': _(
                'Tạo báo cáo dự án'
            ),

            'res_model':
                'sonha.du.an.bao.cao.wizard',

            'view_mode':
                'form',

            'target':
                'new',
        }