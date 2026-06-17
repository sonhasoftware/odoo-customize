/** @odoo-module */
import { patch } from "@web/core/utils/patch";
import { Typing } from "@mail/discuss/typing/common/typing";
import { _t } from "@web/core/l10n/translation";

patch(Typing.prototype, {
    get text() {
        const channel = this.props.channel;
        if (!this.typingService) {
            return super.text;
        }
        const typingMembers = this.typingService.getTypingMembers(channel);
        if (typingMembers.length === 1 && typingMembers[0].persona?.im_status === "agent") {
            return _t("AI is thinking...");
        }
        return super.text;
    },
    get isAiTyping() {
        const channel = this.props.channel;
        if (!this.typingService) {
            return false;
        }
        const typingMembers = this.typingService.getTypingMembers(channel);
        return typingMembers.some(member => member.persona?.im_status === "agent");
    }
});
