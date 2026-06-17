/** @odoo-module */
import { Thread } from "@mail/core/common/thread";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

patch(Thread.prototype, {
    get showStartMessage() {
        return super.showStartMessage || (this.props.thread.type === "ai_chat");
    },
    get startMessageSubtitle() {
        if (this.props.thread.type === "ai_chat") {
            return _t("Hello, what can I help you with?");
        } else {
            return super.startMessageSubtitle;
        }
    },
    onClickPromptButton(button) {
        this.props.thread.post(button);
    },
    get showPromptButtons() {
        return this.props.thread.messages.length === 0;
    },
});
