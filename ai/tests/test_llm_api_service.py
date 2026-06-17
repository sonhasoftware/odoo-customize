import base64

from odoo.tests import common, tagged
from odoo.addons.ai.utils.llm_api_service import LLMApiService
from .test_data import AUDIO_OGG_B64


@tagged("ai_external", "-standard", "post_install", "-at_install")
class TestLLMApiServiceIntegration(common.TransactionCase):
    def test_transcribes_audio_via_external_api(self):
        service = LLMApiService(self.env)
        audio_bytes = base64.b64decode(AUDIO_OGG_B64)
        result = service.get_transcription(audio_bytes, mimetype="audio/ogg")

        self.assertIsInstance(result, str, "Transcription result to be a string")
        self.assertGreater(len(result.strip()), 0, "Transcription result is empty")
        soft_matches = {"transcribing", "things", "transcribe", "thing"}
        score = 0
        for sm in soft_matches:
            if sm in result:
                score += 1
        score /= len(soft_matches)
        self.assertGreaterEqual(score, 0.5, f"Transcription quality is poor  Output: {result!r}")
