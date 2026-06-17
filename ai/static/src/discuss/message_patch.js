/** @odoo-module */
import { Message } from "@mail/core/common/message";
import { patch } from "@web/core/utils/patch";

patch(Message.prototype, {
    get quickActionCount() {
        return this.props.thread?.type === "ai_chat" ? 3 : super.quickActionCount;
    },
});
