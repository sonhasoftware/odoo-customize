/** @odoo-module */
import { AiModelFieldSelectorPopover } from "@ai/ai_model_field_selector/ai_model_field_selector_popover";
import { Plugin } from "@html_editor/plugin";
import { withSequence } from "@html_editor/utils/resource";
import { _t } from "@web/core/l10n/translation";
import { isHtmlContentSupported } from "@html_editor/core/selection_plugin";

export const AI_FIELD_SELECTOR = "span[data-ai-field]";

export class AIFieldSelectorPlugin extends Plugin {
    static id = "AIFieldSelector";
    static dependencies = ["overlay", "selection", "history", "dom"];
    static shared = ["open"];
    resources = {
        user_commands: [
            {
                id: "openAIFieldSelector",
                title: _t("Field Selector"),
                description: _t("Insert a field"),
                icon: _t("fa-hashtag"),
                run: () => this.open(),
                isAvailable: isHtmlContentSupported,
            },
        ],
        normalize_handlers: withSequence(-1, this.normalize.bind(this)),
        powerbox_categories: { id: "ai_prompt_tools", name: _t("AI Prompt Tools") },
        powerbox_items: { categoryId: "ai_prompt_tools", commandId: "openAIFieldSelector" },
        selectors_for_feff_providers: () => AI_FIELD_SELECTOR,
    };

    setup() {
        /** @type {import("@html_editor/core/overlay_plugin").Overlay} */
        this.overlay = this.dependencies.overlay.createOverlay(AiModelFieldSelectorPopover, {
            hasAutofocus: true,
            className: "popover",
        });
    }

    normalize(element) {
        // make sure fields are always protected (could be added without this plugin)
        for (const fieldEl of element.querySelectorAll(AI_FIELD_SELECTOR)) {
            fieldEl.dataset.oeProtected = true;
        }
    }

    open(fieldsPath) {
        this.overlay.open({
            props: {
                close: this.close.bind(this),
                resModel: this.config.fieldSelectorResModel,
                aiFieldPath: this.config.aiFieldPath,
                followRelations: true,
                isDebugMode: this.config.debug,
                showSearchInput: true,
                update: (path, field) => {},
                updateBatch: (fieldsInfo) => this.insert(fieldsInfo),
                fieldsPath: fieldsPath,
            },
        });
    }

    close() {
        this.overlay.close();
        this.dependencies.selection.focusEditable();
    }

    /**
     * Insert the given fields as <span data-ai-field="path">name</span>
     *
     * @param {Array} fieldsInfo: list of field to insert
     */
    insert(fieldsInfo) {
        if (!fieldsInfo) {
            return;
        }

        for (const fieldInfo of fieldsInfo) {
            const span = document.createElement("span");
            const fieldChain = fieldInfo.map((field) => field.name).join(".");
            span.dataset.aiField = fieldChain;
            span.innerText = fieldInfo.map((field) => field.string).join(" > ");
            this.dependencies.dom.insert(span);
            this.dependencies.dom.insert(fieldInfo === fieldsInfo.at(-1) ? "\u00A0" : ", ");
        }
        this.dependencies.history.addStep();
    }
}
