import { ChatWindow } from "@mail/core/common/chat_window";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";


patch(ChatWindow.prototype, {
    get showForwardOperatorButton() {
        const thread = this.props.chatWindow.thread;
        return thread.channel_type === 'livechat' && thread.ai_agent_id;
    },

    async forwardOperator(ev) {
        let thread = this.props.chatWindow.thread;
        if (thread.channel_type !== "livechat") {
            return;
        }
        // Forwarding can only happen on persisted threads.
        if(thread.isTransient){
            thread = await this.store.env.services["im_livechat.livechat"].persist(thread)
            if (!thread){
                return;
            }
        }
        const result = await rpc("/ai_livechat/forward_operator", {
            channel_id: thread.id,
        });
        if(result['store_data']){
            this.store.insert(result['store_data']);
        }
        if (result['notification']){
            this.store.env.services.notification.add(result['notification'], { type: result['notification_type']});
        }
        if (result['success'] === true){
            thread.readyToSwapDeferred.resolve();
        }
    }
});

