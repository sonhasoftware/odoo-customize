# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.osv import expression

from ..models.mail_message import VAT_TU_CHATTER_SCOPES


VAT_TU_THREAD_MODEL = 'ke.hoach.vat.tu'


class VatTuMailThreadController(http.Controller):

    @staticmethod
    def _scope_domain(thread_model, vat_tu_scope):
        # Chỉ áp dụng filter scope cho đúng model kế hoạch vật tư.
        if thread_model != VAT_TU_THREAD_MODEL or vat_tu_scope not in VAT_TU_CHATTER_SCOPES:
            return []
        # Màn vật tư (vt): xem log scope 'vt' và các message cũ chưa có scope.
        if vat_tu_scope == 'vt':
            return expression.OR([
                [('x_vat_tu_scope', '=', 'vt')],
                [('x_vat_tu_scope', '=', False)],
            ])
        # Màn kinh doanh/sản xuất: chỉ xem đúng scope của mình.
        return [('x_vat_tu_scope', '=', vat_tu_scope)]

    @http.route('/sonha_vat_tu/mail/thread/messages', methods=['POST'], type='json', auth='user')
    def vat_tu_mail_thread_messages(self, thread_model, thread_id, vat_tu_scope=None,
                                    search_term=None, before=None, after=None, around=None, limit=30):
        domain = expression.AND([
            [
                ('res_id', '=', int(thread_id)),
                ('model', '=', thread_model),
                ('message_type', '!=', 'user_notification'),
            ],
            self._scope_domain(thread_model, vat_tu_scope),
        ])

        res = request.env['mail.message']._message_fetch(
            domain,
            search_term=search_term,
            before=before,
            after=after,
            around=around,
            limit=limit,
        )
        if not request.env.user._is_public():
            res['messages'].set_message_done()
        return {**res, 'messages': res['messages'].message_format()}
