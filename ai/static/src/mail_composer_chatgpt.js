/** @odoo-module */
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, markup, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MailComposerChatGPT extends Component {
    static template = "mail.MailComposerChatGPT";
    static props = { ...standardFieldProps };

    setup() {
        this.store = useService("mail.store");
        this.orm = useService("orm");
        this.aiChatLauncher = useService("aiChatLauncher");
        let currentDialog, previousZIndex;
        onMounted(() => {
            currentDialog = document.querySelector(".o-overlay-item:has(.o_dialog");
            if (currentDialog) {
                previousZIndex = currentDialog.style.zIndex;
                // 1020 is the value of the $zindex-sticky which is the z-index value used for the `.o-mail-ChatWindow`
                // See odoo/addons/mail/static/src/core/common/chat_window.scss
                // We use this value to ensure that the dialog that contains this component is rendered below the `.o-mail-ChatWindow`s.
                currentDialog.style.zIndex = "1020";
            }
        });
        onWillUnmount(() => {
            this.store.aiInsertButtonTarget = false;
            if (currentDialog) {
                currentDialog.style.zIndex = previousZIndex;
            }
        });
    }

    async onOpenChatGPTPromptDialogBtnClick() {
        await this.aiChatLauncher.launchAIChat({
            callerComponentName: "mail_composer",
            recordModel: this.props.record.data.model,
            recordId: Number(this.props.record.data.res_ids.slice(1, -1)),
            originalRecordData: this.props.record.data,
            aiSpecialActions: {
                insert: (content) => {
                    const root = document.createElement("div");
                    root.appendChild(content);
                    const { body } = this.props.record.data;
                    // markup: the element of which innerHTML is taken should be safely built
                    this.props.record.update({
                        body: markup(root.innerHTML + (body || "")),
                    });
                },
            },
            channelTitle: this.props.record.data.subject,
            aiChatSourceId: this.props.record.id,
        });
    }
}

export const mailComposerChatGPT = {
    component: MailComposerChatGPT,
    fieldDependencies: [{ name: "body", type: "text" }],
};

registry.category("fields").add("mail_composer_chatgpt", mailComposerChatGPT);
