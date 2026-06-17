/** @odoo-module */
import { _t } from "@web/core/l10n/translation";
import { Plugin } from "@html_editor/plugin";
import { closestElement } from "@html_editor/utils/dom_traversal";
import { withSequence } from "@html_editor/utils/resource";
import { isContentEditable } from "@html_editor/utils/dom_info";
import { unwrapContents } from "@html_editor/utils/dom";
import { MAIN_PLUGINS } from "@html_editor/plugin_sets";
import { user } from "@web/core/user";
import { MAIL_PLUGINS, MAIL_SMALL_UI_PLUGINS } from "@mail/core/common/plugin/plugin_sets";

export class ChatGPTPlugin extends Plugin {
    static id = "chatgpt";
    static dependencies = [
        "baseContainer",
        "selection",
        "history",
        "dom",
        "sanitize",
        "dialog",
        "split",
    ];
    resources = {
        user_commands: [
            {
                id: "openChatGPTDialog",
                title: _t("AI"),
                description: _t("Generate or transform content with AI"),
                run: this.openDialog.bind(this),
                isAvailable: () => user.isInternalUser,
            },
        ],
        toolbar_items: [
            {
                id: "chatgpt",
                groupId: "ai",
                commandId: "openChatGPTDialog",
                namespaces: ["compact", "expanded"],
                icon: "ai-logo-icon",
                isDisabled: this.isNotReplaceableByAI.bind(this),
            },
        ],

        powerbox_categories: withSequence(70, { id: "ai", name: _t("AI Tools") }),
        powerbox_items: {
            keywords: [_t("AI")],
            categoryId: "ai",
            commandId: "openChatGPTDialog",
            icon: "fa-magic",
        },

        power_buttons: withSequence(20, {
            commandId: "openChatGPTDialog",
            icon: "ai-logo-icon",
        }),
    };

    isNotReplaceableByAI(selection = this.dependencies.selection.getEditableSelection()) {
        const isEmpty = !selection.textContent().replace(/\s+/g, "");
        const cannotReplace = this.dependencies.selection
            .getTargetedNodes()
            .find((el) => this.dependencies.split.isUnsplittable(el) || !isContentEditable(el));
        return cannotReplace || isEmpty;
    }

    async openDialog(params = {}) {
        const selection = this.dependencies.selection.getEditableSelection();
        const dialogParams = {
            insert: (content) => {
                const insertedNodes = this.dependencies.dom.insert(content);
                this.dependencies.history.addStep();
                // Add a frame around the inserted content to highlight it for 2
                // seconds.
                const start = insertedNodes?.length && closestElement(insertedNodes[0]);
                const end =
                    insertedNodes?.length &&
                    closestElement(insertedNodes[insertedNodes.length - 1]);
                if (start && end) {
                    const divContainer = this.editable.parentElement;
                    let [parent, left, top] = [
                        start.offsetParent,
                        start.offsetLeft,
                        start.offsetTop - start.scrollTop,
                    ];
                    while (parent && !parent.contains(divContainer)) {
                        left += parent.offsetLeft;
                        top += parent.offsetTop - parent.scrollTop;
                        parent = parent.offsetParent;
                    }
                    let [endParent, endTop] = [end.offsetParent, end.offsetTop - end.scrollTop];
                    while (endParent && !endParent.contains(divContainer)) {
                        endTop += endParent.offsetTop - endParent.scrollTop;
                        endParent = endParent.offsetParent;
                    }
                    const div = document.createElement("div");
                    div.classList.add("o-chatgpt-content");
                    const FRAME_PADDING = 3;
                    div.style.left = `${left - FRAME_PADDING}px`;
                    div.style.top = `${top - FRAME_PADDING}px`;
                    div.style.width = `${
                        Math.max(start.offsetWidth, end.offsetWidth) + FRAME_PADDING * 2
                    }px`;
                    div.style.height = `${endTop + end.offsetHeight - top + FRAME_PADDING * 2}px`;
                    divContainer.prepend(div);
                    setTimeout(() => div.remove(), 2000);
                }
                unwrapContents(insertedNodes[0]);
            },
            ...params,
        };
        dialogParams.baseContainer = this.dependencies.baseContainer.getDefaultNodeName();
        // collapse to end
        let callerComp,
            recordModel,
            recordId,
            recordData,
            recordFields,
            callerId,
            channelTitle,
            textSelection;
        const { resModel, resId, data, fields, id } = this.config.getRecordInfo();
        if (selection.isCollapsed) {
            if (resModel === "mail.compose.message") {
                callerComp = "mail_composer";
                recordModel = data.model;
                recordId = Number(data.res_ids.slice(1, -1)); // resIds should look like so `[id]`, the slice and cast allows to extract the id
                recordData = data;
                channelTitle = data.subject;
                callerId = id;
            } else {
                callerComp = "html_field_record";
                recordModel = resModel;
                recordId = resId;
                recordData = data;
                recordFields = fields;
                channelTitle = data?.display_name || _t("Editor");
                callerId = resId || id;
            }
        } else {
            callerComp = "html_field_text_select";
            recordModel = resModel;
            recordId = resId;
            recordData = data;
            recordFields = fields;
            channelTitle = _t("Text Selection");
            callerId = resId || id;
            textSelection = selection.textContent();
        }
        await this.services.aiChatLauncher.launchAIChat({
            callerComponentName: callerComp,
            recordModel: recordModel,
            recordId: recordId,
            originalRecordData: recordData,
            originalRecordFields: recordFields,
            aiSpecialActions: {
                insert: dialogParams.insert,
            },
            channelTitle: channelTitle,
            aiChatSourceId: callerId,
            textSelection: textSelection,
        });
        if (this.services.ui.isSmall) {
            // TODO: Find a better way and avoid modifying range
            // HACK: In the case of opening through dropdown:
            // - when dropdown open, it keep the element focused before the open
            // - when opening the dialog through the dropdown, the dropdown closes
            // - upon close, the generic code of the dropdown sets focus on the kept element (in our case, the editable)
            // - we need to remove the range after the generic code of the dropdown is triggered so we hack it by removing the range in the next tick
            Promise.resolve().then(() => {
                // If the dialog is opened on a small screen, remove all selection
                // because the selection can be seen through the dialog on some devices.
                this.document.getSelection()?.removeAllRanges();
            });
        }
    }

    destroy() {
        const { resModel } = this.config.getRecordInfo();
        if (resModel !== "mail.compose.message") {
            this.services["mail.store"].aiInsertButtonTarget = false;
        }
        super.destroy();
    }
}

MAIN_PLUGINS.push(ChatGPTPlugin);
MAIL_PLUGINS.push(ChatGPTPlugin);
MAIL_SMALL_UI_PLUGINS.push(ChatGPTPlugin);
