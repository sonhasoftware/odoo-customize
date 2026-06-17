/** @odoo-module */
import { fields, Record } from "@mail/core/common/record";

export class AIPromptButton extends Record {
    static _name = "ai.prompt.button";
    static id = "id";

    thread_id = fields.One("Thread", { inverse: "ai_prompt_buttons" });
}

AIPromptButton.register();
