/** @odoo-module */
import {
    MAIN_EMBEDDINGS,
    READONLY_MAIN_EMBEDDINGS,
} from "@html_editor/others/embedded_components/embedding_sets";
import { aiVoiceTranscriptionEmbeddedComponent } from "./core/voice_transcription";
import { aiReadonlyVoiceTranscriptionEmbeddedComponent } from "./core/readonly_voice_transcription";

MAIN_EMBEDDINGS.push(aiVoiceTranscriptionEmbeddedComponent);
READONLY_MAIN_EMBEDDINGS.push(aiReadonlyVoiceTranscriptionEmbeddedComponent);
