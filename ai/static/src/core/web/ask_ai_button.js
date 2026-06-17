/** @odoo-module */
import { Component, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

export class AskAIButton extends Component {
    static template = "ai.AskAIButton";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        onWillStart(async () => {
            const agent = await this.orm.cache().call("ai.agent", "get_ask_ai_agent", []);
            this.hasAIAgent = Boolean(agent);
        });
    }
    async onAskAIClick() {
        const action = await this.env.services.orm.call("ai.agent", "action_ask_ai", [""]);
        if (action) {
            // Don't await so that the command palette can close immediately
            this.action.doAction(action);
        }
    }
}
