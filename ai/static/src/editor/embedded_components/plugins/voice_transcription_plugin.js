/** @odoo-module */
import { Plugin } from "@html_editor/plugin";
import { EMBEDDED_COMPONENT_PLUGINS } from "@html_editor/plugin_sets";
import { selectElements } from "@html_editor/utils/dom_traversal";
import { parseHTML } from "@html_editor/utils/html";
import { withSequence } from "@html_editor/utils/resource";
import { _t } from "@web/core/l10n/translation";
import { renderToElement } from "@web/core/utils/render";
import { uuid } from "@web/core/utils/strings";

const componentSelector = (id) => `#transcriber-${id}`;

const RECORDER_SELECTOR = "[data-embedded='voice-transcription']";
const NOTES_CONTENT_SELECTOR = "[data-embedded-editable='notesContent']";
const TRANSCRIPT_CONTENT_SELECTOR = "[data-embedded-editable='transcriptContent']";

export class TranscriptionPlugin extends Plugin {
    static id = "voice-transcription";
    static dependencies = ["baseContainer", "dom", "history", "selection", "embeddedComponents"];

    resources = {
        hints: [
            {
                selector: `${RECORDER_SELECTOR} ${NOTES_CONTENT_SELECTOR}:not(:focus) > *:only-child`,
                text: _t("Add notes about your upcoming meeting"),
            },
            {
                selector: `${RECORDER_SELECTOR} ${TRANSCRIPT_CONTENT_SELECTOR}:not(:focus) > *:only-child`,
                text: _t("Start recording to get a real-time transcript of the conversation"),
            },
        ],
        hint_targets_providers: (selectionData, editable) => [
            ...editable.querySelectorAll(
                `${RECORDER_SELECTOR} ${NOTES_CONTENT_SELECTOR}:not(:focus) > *:only-child, ${RECORDER_SELECTOR} ${TRANSCRIPT_CONTENT_SELECTOR}:not(:focus) > *:only-child`
            ),
        ],
        user_commands: [
            {
                id: "openTranscriptDialog",
                title: _t("Voice Transcript"),
                description: _t("Dictate text or record a meeting"),
                run: this.insertTranscriptionComponent.bind(this),
            },
        ],
        powerbox_items: [
            {
                keywords: [_t("AI")],
                categoryId: "ai",
                commandId: "openTranscriptDialog",
                icon: "fa-microphone",
            },
        ],
        mount_component_handlers: this.setupTranscriptionComponent.bind(this),
        normalize_handlers: withSequence(Infinity, this.normalize.bind(this)),
    };

    insertTranscriptionComponent(params = {}) {
        const transcriptBlock = renderToElement("ai.VoiceTranscriptionBlueprint", {
            embeddedProps: JSON.stringify({
                id: uuid(),
            }),
        });
        this.dependencies.dom.insert(transcriptBlock);
        this.dependencies.history.addStep();
    }

    setupTranscriptionComponent({ name, props }) {
        if (name === "voice-transcription") {
            const { resModel, resId } = this.config.getRecordInfo();
            Object.assign(props, {
                resModel,
                resId,
                firstRecordingDate: (id) => this.getFirstRecordingDate(id),
                getTabContent: (id, tabName) => this.getTabContent(id, tabName),
                getTranscriptContent: (id) => this.getTranscriptContent(id),
                onTranscriptionStarted: (id) => this.startTranscription(id),
                onTranscriptionUpdated: (state, componentId, chunkId, textContent) =>
                    this.updateTranscription(state, componentId, chunkId, textContent),
                onRecorderStopped: (id, transcript) => this.updateSummary(id, transcript),
            });
        }
    }

    /**
     * Retrieves the dom content of a tab of the transcription component
     * @param {string} id - the id of the transcription component
     * @param {string} tabName - the name of the tab
     * @returns {HtmlElement} the content of the tab
     */
    getTabContent(id, tabName) {
        return this.editable.querySelector(
            `${componentSelector(id)} #${tabName}-content>[data-embedded-editable]`
        );
    }

    getTranscriptContent(id) {
        const transcriptElements = this.editable.querySelectorAll(
            `${componentSelector(id)} ${TRANSCRIPT_CONTENT_SELECTOR} > :not(:has(b:only-child))`
        );
        const transcript = [];
        transcriptElements.forEach((element) => {
            const innerText = element.innerText.trim();
            if (innerText !== "") {
                transcript.push(innerText);
            }
        });
        return transcript.join("\n");
    }

    /**
     * Retrieves the date of the first recording form the dom
     * @param {string} id - the id of the transcription component
     * @returns {string} the date of the first recording
     */
    getFirstRecordingDate(id) {
        const firstDateElement = this.editable.querySelector(
            `${componentSelector(id)} #transcript-content b`
        );
        return firstDateElement?.textContent;
    }

    startTranscription(id) {
        const today = new Date();
        const timeString = today.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
        });

        const anchorNode = this.editable.querySelector(
            `${componentSelector(id)} #transcript-content>div`
        );
        const textElement = document.createElement("p");
        const boldElement = document.createElement("b");

        boldElement.textContent = `${today.toLocaleDateString()} - ${timeString}`;
        textElement.appendChild(boldElement);
        anchorNode.appendChild(textElement);
        this.dependencies.history.addStep();
    }

    updateTranscription(state, componentId, chunkId = "", textContent = "") {
        switch (state) {
            case "listening": {
                const anchorNode = this.getTabContent(componentId, "transcript");
                const textElement = document.createElement("p");
                textElement.classList.add(
                    "o-ai-transcription-listening",
                    "ps-2",
                    "border-start",
                    "border-2",
                    "border-muted"
                );
                textElement.textContent = _t("AI is listening...");
                anchorNode.appendChild(textElement);
                this.dependencies.history.addStep();
                break;
            }
            case "delta":
                return this.updateDelta(componentId, chunkId, textContent);
            case "completed":
                return this.commitTranscription(componentId, chunkId, textContent);
            case "stopped": {
                const listeningNode = this.editable.querySelector(
                    `${componentSelector(componentId)} .o-ai-transcription-listening`
                );
                listeningNode?.remove();
                this.dependencies.history.addStep();
                break;
            }
        }
    }

    updateDelta(componentId, chunkId, textContent) {
        let textElement = this.editable.querySelector(
            `${componentSelector(componentId)} #current-transcript-${chunkId}`
        );
        if (!textElement) {
            const anchorNode = this.getTabContent(componentId, "transcript");
            const listeningNode = this.editable.querySelector(
                `${componentSelector(componentId)} .o-ai-transcription-listening`
            );
            if (!anchorNode) {
                return null;
            }
            textElement = document.createElement("p");
            textElement.setAttribute("id", `current-transcript-${chunkId}`);
            textElement.classList.add(
                "text-muted",
                "ps-2",
                "border-start",
                "border-2",
                "border-muted"
            );
            if (listeningNode) {
                anchorNode.replaceChild(textElement, listeningNode);
            } else {
                anchorNode.appendChild(textElement);
            }
            this.dependencies.history.addStep();
        }
        textElement.textContent = textElement.textContent + textContent;
        return textElement;
    }

    commitTranscription(componenentId, chunkId, textContent) {
        let currentTranscript = this.editable.querySelector(
            `${componentSelector(componenentId)} #current-transcript-${chunkId}`
        );
        if (!currentTranscript) {
            const anchorNode = this.editable.querySelector(
                `${componentSelector(componenentId)} #transcript-content>div`
            );
            if (!anchorNode) {
                return null;
            }
            currentTranscript = document.createElement("p");
            anchorNode.appendChild(currentTranscript);
        } else {
            currentTranscript.removeAttribute("id");
            currentTranscript.removeAttribute("class");
        }
        currentTranscript.textContent = textContent;
        this.dependencies.history.addStep();
        return currentTranscript;
    }

    updateSummary(componentId, transcript) {
        /** @type {HTMLElement} */
        const anchorNode = this.editable.querySelector(
            `${componentSelector(componentId)} #summary-content>div`
        );

        const existingSummary = anchorNode.querySelector("section");
        const htmlTranscript = parseHTML(document, transcript);
        const summarySection = document.createElement("section");
        summarySection.appendChild(htmlTranscript);

        if (existingSummary === null) {
            anchorNode.appendChild(summarySection);
        } else {
            anchorNode.replaceChild(summarySection, existingSummary);
        }
        this.dependencies.history.addStep();
    }

    normalize(element) {
        for (const emptyRecorderNode of selectElements(
            element,
            `${RECORDER_SELECTOR} [data-embedded-editable]:empty`
        )) {
            const baseContainer = this.dependencies.baseContainer.createBaseContainer();
            baseContainer.appendChild(this.document.createElement("br"));
            emptyRecorderNode.replaceChildren(baseContainer);
        }
    }
}

EMBEDDED_COMPONENT_PLUGINS.push(TranscriptionPlugin);
