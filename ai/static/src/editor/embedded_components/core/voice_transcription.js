/** @odoo-module */
import {
    getEditableDescendants,
    getEmbeddedProps,
    StateChangeManager,
    useEditableDescendants,
    useEmbeddedState,
} from "@html_editor/others/embedded_component_utils";
import { RPCError } from "@web/core/network/rpc";
import { Component, onMounted, onWillStart, useState } from "@odoo/owl";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import VADAudioRecorder from "@ai/vad_audio_recorder";
import { _t } from "@web/core/l10n/translation";

export class VoiceTranscription extends Component {
    static template = "ai.VoiceTranscription";
    static components = {};
    static props = {
        host: { type: Object },
        resModel: { type: String },
        resId: { type: Number, optional: true },
        firstRecordingDate: { type: Function },
        getTabContent: { type: Function },
        getTranscriptContent: { type: Function },
        onTranscriptionStarted: { type: Function },
        onTranscriptionUpdated: { type: Function },
        onRecorderStopped: { type: Function },
    };

    static defaultProps = {
        resId: null,
    };

    setup() {
        this.descendants = useEditableDescendants(this.props.host);
        this.embeddedState = useEmbeddedState(this.props.host);
        this.actionService = useService("action");
        this.notificationService = useService("notification");
        this.orm = useService("orm");
        this.mailStore = useService("mail.store");

        this.supportedLanguages = [];

        this.state = useState({
            isOpened: true,
            isRecording: false,
            currentTab: "notes",
            currentLanguage: user.lang.replace("-", "_"),
            status: "idle",
        });

        const onMessage = (data) => {
            const eventType = data.type;
            if (eventType === "conversation.item.input_audio_transcription.delta") {
                const result = this.props.onTranscriptionUpdated(
                    "delta",
                    this.embeddedState.id,
                    data.item_id,
                    data.delta
                );

                if (result === null) {
                    this.audioRecorder.stopRecording();
                    return;
                }
            } else if (eventType === "conversation.item.input_audio_transcription.completed") {
                const result = this.props.onTranscriptionUpdated(
                    "completed",
                    this.embeddedState.id,
                    data.item_id,
                    data.transcript
                );
                if (result === null) {
                    this.audioRecorder.stopRecording();
                    return;
                }
                this.props.onTranscriptionUpdated(
                    "listening",
                    this.embeddedState.id,
                    null,
                    _t("AI is listening...")
                );
            }
        };
        this.audioRecorder = new VADAudioRecorder(onMessage);

        onWillStart(async () => {
            const languages = await this.orm.call("res.lang", "get_installed", []);
            this.supportedLanguages = languages.map(([code]) => ({
                shortCode: code.split("_")[0],
                code,
            }));

            if (this.audioRecorder.state === "recording") {
                this.embeddedState.status = "recording";
            }

            this.composerPrompts = (
                await this.orm.webSearchRead(
                    "ai.composer",
                    [["interface_key", "=", "voice_transcription_component"]],
                    {
                        specification: {
                            ai_agent: {},
                            default_prompt: {},
                            available_prompts: {
                                fields: {
                                    name: {},
                                },
                            },
                        },
                    }
                )
            ).records[0];
            if (this.embeddedState.hasSummary) {
                this.state.currentTab = "summary";
            }
        });

        onMounted(() => {
            this.state.firstRecordingDate = this.props.firstRecordingDate(this.embeddedState.id);
        });
    }

    setCurrentTab(tabName) {
        if (tabName === "summary") {
            const summaryContent = this.props.getTabContent(this.embeddedState.id, "summary");

            if (summaryContent && summaryContent.innerText.trim() === "") {
                this.updateSummary();
            }
        }

        this.state["currentTab"] = tabName;
    }

    onLanguageChange(event) {
        this.state.currentLanguage = event.target.value;
    }

    async toggleRecording() {
        this.state.isRecording = !this.state.isRecording;
        if (this.embeddedState.status === "idle") {
            const transcriptPrompt = this.props.getTabContent(this.embeddedState.id, "notes");
            try {
                this.embeddedState.status = "waiting";
                await this.audioRecorder.startRecording(
                    this.state.currentLanguage.split("_")[0],
                    transcriptPrompt?.innerText.trim()
                );
                this.embeddedState.status = "recording";
                this.props.onTranscriptionStarted(this.embeddedState.id);
                this.props.onTranscriptionUpdated(
                    "listening",
                    this.embeddedState.id,
                    null,
                    _t("AI is listening...")
                );
                this.setCurrentTab("transcript");
            } catch (error) {
                this.embeddedState.status = "idle";
                this.state.isRecording = false;
                if (error instanceof DOMException && error.name === "NotAllowedError") {
                    this.notificationService.add(
                        _t(
                            "You must allow the access to your microphone to start the recording. Try refreshing the page and start again."
                        ),
                        {
                            title: _t("Access error"),
                            type: "danger",
                        }
                    );
                } else if (
                    error instanceof RPCError &&
                    error.data.name === "odoo.exceptions.UserError"
                ) {
                    this.notificationService.add(error.data.message, {
                        title: _t("User error"),
                        type: "danger",
                    });
                } else {
                    this.notificationService.add(_t("Unable to start the recording."), {
                        title: _t("An error occured"),
                        type: "danger",
                    });
                }
            }
        } else if (this.embeddedState.status === "recording") {
            this.props.onTranscriptionUpdated("stopped", this.embeddedState.id);
            this.audioRecorder.stopRecording();
            this.updateSummary();
        }
    }

    async updateSummary(prompt = "") {
        this.embeddedState.status = "summarizing";
        const summary = await this.getSummary(prompt);
        if (summary) {
            this.props.onRecorderStopped(this.embeddedState.id, summary);
            this.embeddedState.hasSummary = true;
            this.setCurrentTab("summary");
        }
        this.embeddedState.status = "idle";
    }

    async getSummary(prompt = "") {
        const textToSummarize = this.props.getTranscriptContent(this.embeddedState.id);
        if (!this.composerPrompts || !textToSummarize || textToSummarize.trim() === "") {
            return null;
        }

        const summary = await this.orm.call(
            "ai.agent",
            "get_direct_response",
            [this.composerPrompts.ai_agent],
            {
                prompt: `${this.composerPrompts.default_prompt}\n${prompt}\n${textToSummarize}`,
                enable_html_response: true,
            }
        );
        return String(summary);
    }

    async openComposer() {
        this.actionService.doAction(
            {
                type: "ir.actions.act_window",
                name: _t("Share transcript summary"),
                view_mode: "form",
                res_model: "mail.compose.message",
                views: [[false, "form"]],
                target: "new",
                view_id: false,
                context: {
                    default_model: this.props.resModel,
                    default_res_ids: [this.props.resId],
                    default_subject: _t("Share transcript summary"),
                    default_body:
                        this.props.getTabContent(this.embeddedState.id, "summary").innerHTML ?? "",
                    clicked_on_full_composer: true,
                },
            },
            {
                onClose: async () => {
                    const thread = this.mailStore.Thread.get({
                        model: this.props.resModel,
                        id: this.props.resId,
                    });
                    thread?.fetchNewMessages();
                },
            }
        );
    }
}

export const aiVoiceTranscriptionEmbeddedComponent = {
    name: "voice-transcription",
    Component: VoiceTranscription,
    getEditableDescendants: getEditableDescendants,
    getProps: (host) => ({ host }),
    getStateChangeManager: (config) =>
        new StateChangeManager(
            Object.assign(config, {
                getEmbeddedState: (host) => {
                    const props = getEmbeddedProps(host);
                    if (host.dataset.embeddedState) {
                        const currentState = JSON.parse(host.dataset.embeddedState);
                        props.status = currentState.next?.status;
                    }
                    props.status ??= "idle";
                    return props;
                },
                stateToEmbeddedProps: (host, state) => {
                    const props = getEmbeddedProps(host);
                    props.id = state.id;
                    props.hasSummary = state.hasSummary;
                    return props;
                },
            })
        ),
};
