/** @odoo-module */
import {
    getEditableDescendants,
    getEmbeddedProps,
    useEditableDescendants,
} from "@html_editor/others/embedded_component_utils";
import { Component, onMounted, onWillStart, useState } from "@odoo/owl";

export class ReadonlyVoiceTranscription extends Component {
    static template = "ai.ReadonlyVoiceTranscription";
    static components = {};
    static props = {
        host: { type: Object },
    };

    setup() {
        this.descendants = useEditableDescendants(this.props.host);
        this.supportedLanguages = [];
        this.state = useState({
            isOpened: true,
            currentTab: "notes",
        });

        onWillStart(() => {
            if (this.props.hasSummary) {
                this.state.currentTab = "summary";
            }
        });

        onMounted(() => {
            const firstRecordingDate = this.props.host.querySelector("#transcript-content b");
            this.state.firstRecordingDate = firstRecordingDate?.textContent ?? "";
        });
    }

    setCurrentTab(tabName) {
        this.state["currentTab"] = tabName;
    }
}

export const aiReadonlyVoiceTranscriptionEmbeddedComponent = {
    name: "voice-transcription",
    Component: ReadonlyVoiceTranscription,
    getEditableDescendants,
    getProps: (host) => ({ host, ...getEmbeddedProps(host) }),
};
