/** @odoo-module */
import { Composer } from "@mail/core/common/composer";

import { patch } from "@web/core/utils/patch";

patch(Composer.prototype, {
    saveContent() {
        if (this.thread?.type === "ai_chat") {
            return;  // no point in saving the content in an AI chat since chats are independent 
        }
        super.saveContent();
    },
    onFocusin(ev) {
        super.onFocusin(ev);
        if (this.thread?.type === "ai_chat") {
            ev.target.select();
        }
    },
    get wysiwygConfig() {
        const config = super.wysiwygConfig;
        return {
            ...config,
            getRecordInfo: () => {
                return {
                    resModel: this.thread?.model,
                    resId: this.thread?.id,
                };
            },
        };
    },
    get allowUpload() {
        if (this.thread?.type === "ai_chat") {
            return false;
        }
        return super.allowUpload;
    }
});
