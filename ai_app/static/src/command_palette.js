/** @odoo-module */
import { cleanTerm } from "@mail/utils/common/format";
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { url } from "@web/core/utils/urls";

const commandProviderRegistry = registry.category("command_provider");
const commandCategoryRegistry = registry.category("command_categories");

commandCategoryRegistry.add("AI_AGENTS", { namespace: "@", name: _t("Agents") }, { sequence: 30 });

export class AICommand extends Component {
    static template = "ai_app.AICommand";
    static props = {
        executeCommand: Function,
        name: String,
        subtitle: String,
        imgUrl: String,
        action: { type: Object, optional: true },
        searchValue: String,
        slots: Object,
    };

    setup() {
        super.setup();
        this.ui = useService("ui");
    }
}
export class AICommandPalette {
    constructor(env, options) {
        this.env = env;
        this.options = options;
        this.orm = env.services.orm;
        this.ui = env.services.ui;
        this.actions = env.services.action;
        this.commands = [];
        this.options = options;
        this.cleanedTerm = cleanTerm(this.options.searchValue);
        this.agents = [];
    }

    async fetch() {
        this.agents = await this.orm.searchRead(
            "ai.agent",
            [["is_system_agent", "=", false]],
            ["id", "name", "subtitle", "partner_id"],
            { load: false }
        );
    }

    async buildResults(filtered) {
        this.agents
            .filter(
                (agent) =>
                    (cleanTerm(agent.name).includes(this.cleanedTerm) ||
                        (agent.subtitle && cleanTerm(agent.subtitle).includes(this.cleanedTerm))) &&
                    (!filtered || !filtered.has(agent))
            )
            .slice(0, 5)
            .forEach((agent) => {
                this.commands.push({
                    Component: AICommand,
                    action: async () => {
                        const result = await this.orm.call("ai.agent", "open_agent_chat", [
                            agent.id,
                        ]);
                        if (result) {
                            this.actions.doAction(result);
                        }
                    },
                    name: agent.name,
                    props: {
                        imgUrl: url('/web/image', { model: 'ai.agent', id: agent.id, field: 'image_128' }),
                        subtitle: agent.subtitle ? agent.subtitle : "",
                    },
                    category: "AI_AGENTS",
                });
            });
    }
}

commandProviderRegistry.add("chat_with_agent", {
    namespace: "@",
    async provide(env, options) {
        const palette = new AICommandPalette(env, options);
        await palette.fetch();
        palette.buildResults();
        return palette.commands;
    },
});
