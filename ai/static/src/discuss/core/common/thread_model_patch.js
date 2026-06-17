/** @odoo-module */
import { ThreadService } from "@mail/core/common/thread_service";
import { patch } from "@web/core/utils/patch";
import { RPCError } from "@web/core/network/rpc_service";
import { _t } from "@web/core/l10n/translation";
import { getCurrentViewInfo } from "@ai/discuss/core/common/view_details";
import { session } from "@web/session";

patch(ThreadService.prototype, {
    async post(thread, body, postData = {}) {
        const message = await super.post(thread, body, postData);
        const aiMember = thread.channelMembers?.find(
            (member) => member.persona?.im_status == "agent"
        );
        // message could be undefined if it is a command, for example /help.
        if (message && thread.type === "ai_chat") {
            try {
                if (aiMember) {
                    aiMember.isTyping = true;
                    if (this.env.services["discuss.typing"]) {
                        this.env.services["discuss.typing"].addTypingMember(aiMember);
                    }
                }
                await this.rpc("/ai/generate_response", {
                    mail_message_id: message.id,
                    channel_id: thread.id,
                    current_view_info: await getCurrentViewInfo(this.env.bus),
                    ai_session_identifier: session.ai_session_identifier,
                });
            } catch (error) {
                if (error instanceof RPCError) {
                    await this.rpc("/ai/post_error_message", {
                        error_message:
                            error.data?.message ||
                            _t("An error occurred while generating the AI response."),
                        channel_id: thread.id,
                    });
                } else {
                    throw error;
                }
            } finally {
                if (aiMember) {
                    aiMember.isTyping = false;
                    if (this.env.services["discuss.typing"]) {
                        this.env.services["discuss.typing"].removeTypingMember(aiMember);
                    }
                }
            }
        }
        return message;
    },
});
