# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import http
from odoo.http import request

from ..utils.llm_api_service import LLMApiService, RealtimeParameters

DEFAULT_TOKEN_LIFESPAN = 7200  # Token lifespan in seconds
DEFAULT_SILENCE_DURATION = 500  # Silence duration in ms


class AgentController(http.Controller):

    @http.route(["/ai/transcription/session"], methods=["POST"], type="json", auth="user", readonly=True)
    def get_session_token(self, language: str, prompt: str):
        service = LLMApiService(request.env)

        session_params: RealtimeParameters = {
            "expires_after": {"anchor": "created_at", "seconds": DEFAULT_TOKEN_LIFESPAN},
            "session": {
                "type": "transcription",
                "audio": {
                    "input": {
                        "transcription": {
                            "language": language,
                            "model": "gpt-4o-transcribe",
                            "prompt": prompt,
                        },
                        "turn_detection": {
                            "type": "server_vad",
                            "silence_duration_ms": DEFAULT_SILENCE_DURATION,
                        },
                        "noise_reduction": {"type": "far_field"},
                    }
                },
            },
        }

        session = service.get_transcription_session(session_params)
        return session
