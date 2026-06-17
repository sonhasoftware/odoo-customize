# -*- coding: utf-8 -*-

from odoo import models, api, _
import html
import logging
from markupsafe import Markup

_logger = logging.getLogger(__name__)

class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        # Allow the actual message to be posted first
        message = super(MailThread, self).message_post(**kwargs)

        try:
            # We only care about human messages (not system notes or bot replies)
            if message.author_id and message.message_type == 'comment':
                ai_partner = self.env.ref('sonha_ai.partner_sonha_ai', raise_if_not_found=False)
                
                # Check if AI partner exists and is NOT the author (prevent infinite loops)
                if ai_partner and message.author_id.id != ai_partner.id:
                    
                    is_ai_mentioned = False
                    
                    # 1. Check if AI is mentioned in the message
                    if ai_partner.id in message.partner_ids.ids:
                        is_ai_mentioned = True
                        
                    # 2. Check if this is a Direct Message (channel) with the AI
                    if not is_ai_mentioned and message.model == 'discuss.channel':
                        channel = self.env['discuss.channel'].sudo().browse(message.res_id)
                        if channel.exists() and channel.channel_type == 'chat':
                            if ai_partner.id in channel.channel_member_ids.mapped('partner_id').ids:
                                is_ai_mentioned = True

                    if is_ai_mentioned:
                        # Extract raw text from HTML body
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(message.body, 'html.parser')
                        raw_text = soup.get_text(separator=' ', strip=True)
                        
                        # Remove the mention name from the text if it exists (e.g., "@Sonha AI Assistant")
                        mention_text = f"@{ai_partner.name}"
                        if mention_text in raw_text:
                            raw_text = raw_text.replace(mention_text, '').strip()
                        elif ai_partner.name in raw_text:
                            raw_text = raw_text.replace(ai_partner.name, '').strip()
                            
                        if not raw_text:
                            raw_text = "Chào bạn"

                        # Build context
                        model_name = message.model if message.model != 'discuss.channel' else None
                        record_id = message.res_id if model_name else None
                        
                        # Call AI Logic
                        _logger.info("Sonha AI Discuss Intercept: Triggering AI for prompt: %s", raw_text)
                        
                        # We use a new transaction/env or sudo to run this, 
                        # but doing it synchronously might freeze the UI for the user posting.
                        # For now, we do it synchronously to ensure the response appears.
                        
                        resp = self.env['sonha.ai.bot'].sudo().process_chat(
                            prompt=raw_text,
                            model_name=model_name,
                            record_id=record_id
                        )
                        
                        if 'result' in resp:
                            ai_reply = resp['result']
                            
                            # If it's a chart, we can't draw Chart.js in Discuss, so we explain
                            if 'chartData' in resp or 'multiChartData' in resp:
                                ai_reply += "\n\n*(Lưu ý: Để xem biểu đồ động trực quan, vui lòng copy câu hỏi này và dán vào Chatbox Sonha AI ở góc dưới màn hình. Khung chat này chỉ hỗ trợ hiển thị văn bản).* "
                                
                            # Convert text to basic HTML with line breaks
                            ai_reply_html = ai_reply.replace('\n', '<br/>')
                            
                            # Reply to the same thread as the AI Partner
                            super(MailThread, self).message_post(
                                body=Markup(ai_reply_html),
                                author_id=ai_partner.id,
                                message_type='comment',
                                subtype_xmlid='mail.mt_comment',
                                # We post back to the same record
                                model=message.model,
                                res_id=message.res_id,
                            )
                        elif 'error' in resp:
                            error_html = f"Lỗi AI: {resp['error']}"
                            super(MailThread, self).message_post(
                                body=Markup(error_html),
                                author_id=ai_partner.id,
                                message_type='comment',
                                subtype_xmlid='mail.mt_comment',
                                model=message.model,
                                res_id=message.res_id,
                            )
        except Exception as e:
            _logger.error("Sonha AI Discuss Error: %s", str(e))
            
        return message
