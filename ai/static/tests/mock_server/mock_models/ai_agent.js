import { fields, models } from "@web/../tests/web_test_helpers";

export class AIAgent extends models.ServerModel {
    _name = "ai.agent";

    name = fields.Char();
    partner_id = fields.Many2one({
        relation: "res.partner",
    });

    get_direct_response(prompt, enable_html_response) {
        return ["This is a response"];
    }

    open_agent_chat() {
        const agent = this[0];
        const partner = this.env["res.partner"].browse(agent.partner_id);
        const channelId = this.env["discuss.channel"]._get_or_create_ai_chat(partner[0]);
        return {
            type: "ir.actions.client",
            tag: "agent_chat_action",
            params: {
                channelId,
            },
        };
    }
}
