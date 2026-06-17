import { ChatWindow } from "@mail/core/common/chat_window_model";
import { patch } from "@web/core/utils/patch";

patch(ChatWindow.prototype, {
    _onClose(options = {}) {
        const channel = this.thread;
        super._onClose(options);
        if(channel?.model === 'discuss.channel'){
            this.store.env.bus.trigger('CHATWINDOW_CLOSED', { channel });
        }
    },
});
