/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { ThreadAction } from "@mail/core/common/thread_actions";

patch(ThreadAction.prototype, {
    _condition({ action, thread }) {
        const requiredActions = ["close", "fold-chat-window", "expand-discuss"];
        if (thread?.type === "ai_chat" && !requiredActions.includes(action.id)) {
            return false;
        }
        return super._condition(...arguments);
    },
});
