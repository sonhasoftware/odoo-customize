import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { animationFrame, queryOne } from "@odoo/hoot-dom";
import { TranscriptionPlugin } from "../src/editor/embedded_components/plugins/voice_transcription_plugin";
import { aiVoiceTranscriptionEmbeddedComponent } from "../src/editor/embedded_components/core/voice_transcription";
import {
    defineModels,
    fields,
    makeMockServer,
    models,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { renderToString } from "@web/core/utils/render";
import VADAudioRecorder from "../src/vad_audio_recorder";
import { defineAIModels } from "./ai_test_helpers";
import { contains, click } from "@mail/../tests/mail_test_helpers";
import {
    setupMultiEditor,
    validateSameHistory,
} from "@html_editor/../tests/_helpers/collaboration";
import { addStep, tripleClick } from "@html_editor/../tests/_helpers/user_actions";
import { cleanHints } from "@html_editor/../tests/_helpers/dispatch";
import { parseHTML } from "@html_editor/utils/html";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";
import { setupEditor } from "@html_editor/../tests/_helpers/editor";
import { EmbeddedComponentPlugin } from "@html_editor/others/embedded_component_plugin";

class Dummy extends models.Model {
    _name = "dummy";

    name = fields.Char();
    message_ids = fields.One2many({
        relation: "mail.message",
        string: "Messages",
    });

    _records = [
        { id: 1, name: "Bob" },
        { id: 2, name: "Patrick" },
        { id: 3, name: "Sheldon" },
    ];
}

defineModels([Dummy]);
defineAIModels();

beforeEach(() => {
    onRpc("ai.composer", "web_search_read", () => ({
        records: [{}],
    }));

    patchWithCleanup(VADAudioRecorder.prototype, {
        startRecording() {
            this.state = "recording";
            if (VADAudioRecorder.socket === null) {
                VADAudioRecorder.socket = new WebSocket();
            }
            VADAudioRecorder.socket.addEventListener("message", (event) => {
                const jsonData = JSON.parse(event.data);
                this.onMessage(jsonData);
            });
        },
        stopRecording() {
            this.state = "stopped";
        },
    });
});

function getCurrentDate() {
    const today = new Date();
    const timeString = today.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
    });
    return `${today.toLocaleDateString()} - ${timeString}`;
}

const testAiVoiceTranscriptionEmbeddedComponent = {
    ...aiVoiceTranscriptionEmbeddedComponent,
    Component: class AudioTranscriber extends aiVoiceTranscriptionEmbeddedComponent.Component {
        static props = ["*"];
    },
};

const config = {
    Plugins: [...MAIN_PLUGINS, EmbeddedComponentPlugin, TranscriptionPlugin],
    resources: {
        embedded_components: [testAiVoiceTranscriptionEmbeddedComponent],
    },
    getRecordInfo: () => ({
        resModel: "dummy",
        resId: "1",
    }),
    collaboration: {
        peerId: 1,
    },
};

describe("Component behaviour", () => {
    test.tags("desktop");
    test("transcript component tabs have proper hints", async () => {
        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);
        expect("button:contains(Notes)").toHaveClass("active");
        expect("[data-embedded-editable='notesContent'] .o-we-hint").toHaveAttribute(
            "o-we-hint-text",
            "Add notes about your upcoming meeting"
        );
        await click("button:contains(Transcript)");
        await animationFrame();
        expect("button:contains(Transcript)").toHaveClass("active");
        expect("[data-embedded-editable='transcriptContent'] .o-we-hint").toHaveAttribute(
            "o-we-hint-text",
            "Start recording to get a real-time transcript of the conversation"
        );
        await tripleClick(queryOne("[data-embedded-editable='transcriptContent'] .o-we-hint>br"));
        await animationFrame();
        expect("[data-embedded-editable='transcriptContent'] .o-we-hint").toHaveAttribute(
            "o-we-hint-text",
            'Type "/" for commands'
        );
    });

    test("transcription items are properly rendered", async () => {
        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);
        await click("button:contains(Start Recording)");
        await animationFrame();
        expect("button:contains(Transcript)").toHaveClass("active");
        expect("[data-embedded-editable='transcriptContent'] p>b").toHaveText(getCurrentDate());

        expect(".o-ai-transcription-listening").toHaveText("AI is listening...");

        const socket = VADAudioRecorder.socket;
        socket.dispatchEvent(
            new MessageEvent("message", {
                data: JSON.stringify({
                    item_id: 1,
                    type: "conversation.item.input_audio_transcription.delta",
                    delta: "This is",
                }),
            })
        );
        expect("#current-transcript-1").toHaveText("This is");
        socket.dispatchEvent(
            new MessageEvent("message", {
                data: JSON.stringify({
                    item_id: 1,
                    type: "conversation.item.input_audio_transcription.delta",
                    delta: " a test",
                }),
            })
        );
        expect("#current-transcript-1").toHaveText("This is a test");

        socket.dispatchEvent(
            new MessageEvent("message", {
                data: JSON.stringify({
                    item_id: 1,
                    type: "conversation.item.input_audio_transcription.completed",
                    transcript: "This is a test of transcription",
                }),
            })
        );
        await click("button:contains(Stop Recording)");
        await animationFrame();
        expect("#current-transcript-1").toHaveCount(0);
        expect(".o-ai-transcription-listening").toHaveCount(0);
        expect("[data-embedded-editable='transcriptContent'] p:last-child").toHaveText(
            "This is a test of transcription"
        );
    });

    test("should only summarize when there is content in the transcription tab", async () => {
        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);
        expect("[data-embedded-editable='summaryContent'] section").toHaveCount(0);
        expect("button:contains(Summary)").toHaveCount(0);

        await click("button:contains(Start Recording)");
        await click("button:contains(Stop Recording)");
        expect("[data-embedded-editable='summaryContent'] section").toHaveCount(0);

        await click("button:contains(Start Recording)");

        VADAudioRecorder.socket.dispatchEvent(
            new MessageEvent("message", {
                data: JSON.stringify({
                    item_id: 1,
                    type: "conversation.item.input_audio_transcription.completed",
                    transcript: "This is a test of transcription",
                }),
            })
        );

        await click("button:contains(Stop Recording)");
        await contains("button.active:contains(Summary)");
        await contains("[data-embedded-editable='summaryContent'] section", {
            textContent: "This is a response",
        });
    });

    test("share composer should have summary content", async () => {
        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        const server = await makeMockServer();
        server.env["mail.compose.message"]._views.form = `
            <form>
                <field name="body" type="html" widget="html_composer_message"/>
            </form>
        `;

        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);

        await click("button:contains(Start Recording)");

        VADAudioRecorder.socket.dispatchEvent(
            new MessageEvent("message", {
                data: JSON.stringify({
                    item_id: 1,
                    type: "conversation.item.input_audio_transcription.completed",
                    transcript: "This is a test of transcription",
                }),
            })
        );

        await click("button:contains(Stop Recording)");
        await click("[data-embedded='voice-transcription'] button:contains(Share by email)");
        await animationFrame();
        expect("div[name='body'] section").toHaveText("This is a response");
    });

    test("summary has proper prompt actions", async () => {
        onRpc("ai.composer", "web_search_read", () => ({
            records: [
                {
                    ai_agent: 1,
                    default_prompt: "This is a default prompt",
                    available_prompts: [
                        {
                            name: "Summarize this prospect call",
                        },
                        {
                            name: "Write an email recap",
                        },
                    ],
                },
            ],
        }));

        const transcriptBlock = renderToString("ai.VoiceTranscriptionBlueprint");
        const server = await makeMockServer();
        server.env["mail.compose.message"]._views.form = `
        <form>
            <field name="body" type="html" widget="html_composer_message"/>
        </form>
        `;

        await setupEditor(`<p>[]</p>${transcriptBlock}`, {
            config,
        });

        expect("[data-embedded='voice-transcription']").toHaveCount(1);

        await click("button:contains(Start Recording)");

        VADAudioRecorder.socket.dispatchEvent(
            new MessageEvent("message", {
                data: JSON.stringify({
                    item_id: 1,
                    type: "conversation.item.input_audio_transcription.completed",
                    transcript: "This is a test of transcription",
                }),
            })
        );

        await click("button:contains(Stop Recording)");
        await animationFrame();
        expect(
            "[data-embedded='voice-transcription'] button:contains(Summarize this prospect call)"
        ).toHaveCount(1);
        expect(
            "[data-embedded='voice-transcription'] button:contains(Write an email recap)"
        ).toHaveCount(1);
    });
});

describe("Collaboration on transcription component", () => {
    test("recording and summarization are synchronized between peers", async () => {
        const peerInfos = await setupMultiEditor({
            peerIds: ["c1", "c2"],
            contentBefore: "<p>[c1}{c1][c2}{c2]<br></p>",
            ...config,
        });

        Object.values(peerInfos).forEach((peer) => {
            peer.editor.config.getRecordInfo = config.getRecordInfo;
        });

        const editor1 = peerInfos.c1.editor;
        const editor2 = peerInfos.c2.editor;

        editor1.shared.dom.insert(
            parseHTML(editor1.document, renderToString("ai.VoiceTranscriptionBlueprint"))
        );
        addStep(editor1);
        peerInfos.c2.collaborationPlugin.onExternalHistorySteps(peerInfos.c1.historyPlugin.steps);
        validateSameHistory(peerInfos);
        cleanHints(editor2);
        expect(editor2.editable.querySelector("[data-embedded='voice-transcription']")).toHaveCount(
            1
        );
        await animationFrame();
        await click(editor1.editable.querySelector("summary>div button:last-child"));
        addStep(editor1);
        peerInfos.c2.collaborationPlugin.onExternalHistorySteps(peerInfos.c1.historyPlugin.steps);
        await animationFrame();
        expect(editor2.editable.querySelector("summary>div button:last-child")).toHaveText(
            "Stop Recording"
        );
        expect(
            editor2.editable.querySelector("[data-embedded-editable='transcriptContent'] p>b")
        ).toHaveText(getCurrentDate());

        VADAudioRecorder.socket.dispatchEvent(
            new MessageEvent("message", {
                data: JSON.stringify({
                    item_id: 1,
                    type: "conversation.item.input_audio_transcription.completed",
                    transcript: "This is a test of transcription",
                }),
            })
        );

        await animationFrame();

        await click(editor1.editable.querySelector("summary>div button:last-child"));
        addStep(editor1);
        await animationFrame();
        addStep(editor1);
        peerInfos.c2.collaborationPlugin.onExternalHistorySteps(peerInfos.c1.historyPlugin.steps);

        await click(editor2.editable.querySelector("summary>nav button:first-child"));
        await animationFrame();

        expect(
            editor2.editable.querySelector("[data-embedded-editable='summaryContent'] section")
        ).toHaveText("This is a response");
    });
});
