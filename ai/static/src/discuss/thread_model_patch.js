/** @odoo-module */
import { Thread } from "@mail/core/common/thread_model";
import { patch } from "@web/core/utils/patch";
import { fields } from "@mail/core/common/record";
import { browser } from "@web/core/browser/browser";

const AI_PROMPT_BUTTONS = "ai.thread.prompt_buttons.";

patch(Thread.prototype, {
    setup() {
        super.setup();
        this.ai_prompt_buttons = fields.Many("ai.prompt.button", {
            inverse: "thread_id",
            compute() {
                return JSON.parse(browser.localStorage.getItem(AI_PROMPT_BUTTONS.concat(this.id)));
            },
        });
    },
    async closeChatWindow(options = {}) {
        await super.closeChatWindow(options);
        browser.localStorage.removeItem(AI_PROMPT_BUTTONS.concat(this.id));
    },
    get avatarUrl() { 
        if (this.type === "ai_chat" && this.correspondent) {
            return this.correspondent.avatarUrl;
        }

        return super.avatarUrl;
    },
});
