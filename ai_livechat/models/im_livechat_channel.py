from odoo import api, fields, models


class Im_LivechatChannel(models.Model):
    _inherit = 'im_livechat.channel'

    ai_agent_count = fields.Integer(string='Number of AI Agents', compute='_compute_ai_agent_count')

    @api.depends('rule_ids.ai_agent_id')
    def _compute_ai_agent_count(self):
        count_by_channel = dict(self.env['im_livechat.channel.rule']._read_group(
            [('channel_id', 'in', self.ids)], ['channel_id'], ['ai_agent_id:count_distinct']))
        for channel in self:
            channel.ai_agent_count = count_by_channel.get(channel.id, 0)

    def _is_livechat_available(self):
        is_livechat_available = super()._is_livechat_available()
        return is_livechat_available or self.ai_agent_count

    def _get_agent_member_vals(self, /, *, last_interest_dt, now, chatbot_script, operator_partner, operator_model, **kwargs):
        agent_member_vals = super()._get_agent_member_vals(
            last_interest_dt=last_interest_dt,
            now=now,
            chatbot_script=chatbot_script,
            operator_partner=operator_partner,
            operator_model=operator_model,
            **kwargs
        )
        agent_member_vals['ai_agent_id'] = kwargs.get('ai_agent', False)
        return agent_member_vals

    def _get_operator_info(self, /, *, lang, country_id, previous_operator_id=None, chatbot_script_id=None, **kwargs):
        operator_info = super()._get_operator_info(
            lang=lang,
            country_id=country_id,
            previous_operator_id=previous_operator_id,
            chatbot_script_id=chatbot_script_id,
            **kwargs
        )
        # sudo() => access is managed through _is_user_access_allowed.
        ai_agent = self.env['ai.agent'].sudo().search([('id', '=', kwargs.get('ai_agent_id'))])
        if ai_agent and ai_agent._is_user_access_allowed():
            operator_info.update({
                'operator_model': 'ai.agent',
                'ai_agent': ai_agent,
                'operator_partner': ai_agent.partner_id,
            })
        return operator_info

    def _get_channel_name(self, /, *, visitor_user=None, guest=None, agent, chatbot_script, operator_model, **kwargs):
        is_ai_agent = operator_model == 'ai.agent'
        if is_ai_agent is False:
            return super()._get_channel_name(
                visitor_user=visitor_user,
                guest=guest,
                agent=agent,
                chatbot_script=chatbot_script,
                operator_model=operator_model,
                **kwargs
            )
        return kwargs['ai_agent'].name
