# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import json
import logging
import re
import io
import base64

_logger = logging.getLogger(__name__)

class SonhaAIController(http.Controller):

    @http.route('/sonha_ai/chat', type='json', auth='user')
    def chat_with_ai(self, prompt, model_name=None, record_id=None, chatter_messages=None):
        try:
            resp = request.env['sonha.ai.bot'].process_chat(
                prompt=prompt,
                model_name=model_name,
                record_id=record_id,
                chatter_messages=chatter_messages
            )
            
            # Test JSON serialization to prevent 500 Internal Server Error in Odoo framework
            try:
                json.dumps(resp)
            except Exception as ser_ex:
                _logger.error("JSON Serialization Error: %s", str(ser_ex))
                # Fallback to stringifying everything to force it to work
                safe_resp = {"error": f"Lỗi đóng gói dữ liệu (Serialization): {str(ser_ex)}. Vui lòng kiểm tra log."}
                return safe_resp
                
            return resp
            
        except Exception as e:
            _logger.error("Sonha AI General Error: %s", str(e))
            return {"error": str(e)}
