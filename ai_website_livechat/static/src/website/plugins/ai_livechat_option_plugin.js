import { Plugin } from "@html_editor/plugin";
import { registry } from "@web/core/registry";
import { BuilderAction } from "@html_builder/core/builder_action";
import { withSequence } from "@html_editor/utils/resource";
import { after } from "@html_builder/utils/option_sequence";
import { WEBSITE_BACKGROUND_OPTIONS } from "@website/builder/option_sequence";
import { AILivechatOption } from "./ai_livechat_option";

async function update_website_snippet_agent ({ ormService, newAgentId=null, oldAgentId=null }) {
    let agent_ids = {}
    if(newAgentId){
        agent_ids.new_agent_id = parseInt(newAgentId);
    }
    if(oldAgentId){
        agent_ids.old_agent_id = parseInt(oldAgentId);
    }
    await ormService.call(
        "ai.agent",
        "update_website_snippet_agent",
        [],
        agent_ids,
    );
}

class AILivechatOptionPlugin extends Plugin {
    static id = "aiLivechatOption";

    resources = {
        so_content_addition_selector: [".s_ai_livechat"],
        builder_options: [
            withSequence(after(WEBSITE_BACKGROUND_OPTIONS), {
                OptionComponent: AILivechatOption,
                template: "ai_website_livechat.AILivechatOption",
                selector: ".s_ai_livechat",
            }),
        ],
        builder_actions: {
            SetChatStyleAction,
            SetAIAgentAction,
            SetLivechatChannelAction,
            SetPromptPlaceholderAction,
            ToggleHasFallbackButtonAction,
            SetFallbackButtonTextAction,
            SetFallbackButtonURLAction,
        },
        on_snippet_dropped_handlers: this.onSnippetDropped.bind(this),
        on_will_remove_handlers: this.onWillRemove.bind(this),
    };

    async onSnippetDropped({ snippetEl }) {
        if (snippetEl.matches('.s_ai_livechat')) {
            const aiAgentId = await this.services.orm.search(
                "ai.agent",
                ["|", ["livechat_channel_rule_ids", "!=", false], ["used_on_website_snippet", "=", true]],
                { limit: 1 }
            );
            if(aiAgentId){;
                snippetEl.dataset.agentId = aiAgentId;
            }
        }
    }

    async onWillRemove(toRemoveEl) {
        if (toRemoveEl.matches(".s_ai_livechat")) {
            const aiAgentId = toRemoveEl.dataset.agentId;
            if (aiAgentId){
                await update_website_snippet_agent({ ormService: this.services.orm, oldAgentId: aiAgentId });
            }
        }
    }
}

export class SetAIAgentAction extends BuilderAction {
    static id = "setAIAgent";

    getValue ({ editingElement }) {
        const agentId = editingElement.dataset.agentId;
        if (!agentId) {
            return undefined;
        }
        return JSON.stringify({ id: parseInt(agentId) });
    }

    async apply ({ editingElement, value }) {
        const id = value ? JSON.parse(value).id : "";
        editingElement.dataset.agentId = id;
        await update_website_snippet_agent({
            ormService: this.services.orm,
            newAgentId: id,
            oldAgentId: editingElement.dataset.agentId
        })
    }

    async clean({ editingElement }) {
        const oldAgentId = editingElement.dataset.agentId;
        editingElement.dataset.agentId = "";
        await update_website_snippet_agent({ ormService: this.services.orm, oldAgentId: oldAgentId })
    }
}

export class SetLivechatChannelAction extends BuilderAction {
    static id = "setLivechatChannel";

    getValue ({ editingElement }) {
        const livechatChannelId = editingElement.dataset.livechatChannelId;
        if (!livechatChannelId) {
            return undefined;
        }
        return JSON.stringify({ id: parseInt(livechatChannelId) });
    }

    apply ({ editingElement, value }) {
        const id = value ? JSON.parse(value).id : "";
        editingElement.dataset.livechatChannelId = id;
    }

    clean({ editingElement }) {
        editingElement.dataset.livechatChannelId = "";
    }
}

export class SetChatStyleAction extends BuilderAction {
    static id = "setChatStyle";

    isApplied ({ editingElement, params: { mainParam: chatStyle } }) {
        if (!editingElement.dataset.chatStyle) {
            editingElement.dataset.chatStyle = "fullscreen";
        }
        return editingElement.dataset.chatStyle === chatStyle;
    }

    apply ({ editingElement, params: { mainParam: chatStyle } }) {
        editingElement.dataset.chatStyle = chatStyle;
    }
}

export class SetPromptPlaceholderAction extends BuilderAction {
    static id = "setPromptPlaceholder";

    getValue ({ editingElement }) {
        const promptPlaceholder = editingElement.dataset.promptPlaceholder;
        if (!promptPlaceholder) {
            return "";
        }
        return promptPlaceholder;
    }

    apply ({ editingElement, value }) {
        editingElement.dataset.promptPlaceholder = value;
    }
}

export class ToggleHasFallbackButtonAction extends BuilderAction {
    static id = "toggleHasFallbackButton";

    isApplied ({ editingElement }) {
        return editingElement.dataset.hasFallbackButton === "true";
    }

    apply ({ editingElement }) {
        const value = editingElement.dataset.hasFallbackButton === "true" ? false : true;
        editingElement.dataset.hasFallbackButton = value;
    }
}

export class SetFallbackButtonTextAction extends BuilderAction {
    static id = "setFallbackButtonText";

    getValue ({ editingElement }) {
        const fallbackButtonText = editingElement.dataset.fallbackButtonText;
        if (!fallbackButtonText) {
            return "";
        }
        return fallbackButtonText;
    }

    apply ({ editingElement, value }) {
        editingElement.dataset.fallbackButtonText = value;
    }
}

export class SetFallbackButtonURLAction extends BuilderAction {
    static id = "setFallbackButtonURL";

    getValue ({ editingElement }) {
        const fallbackButtonURL = editingElement.dataset.fallbackButtonURL;
        if (!fallbackButtonURL) {
            return "";
        }
        return fallbackButtonURL;
    }

    apply ({ editingElement, value }) {
        editingElement.dataset.fallbackButtonURL = value;
    }
}

registry.category("website-plugins").add(AILivechatOptionPlugin.id, AILivechatOptionPlugin);
