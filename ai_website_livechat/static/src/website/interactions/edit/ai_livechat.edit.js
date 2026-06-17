import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";


export class AILivechatEdit extends Interaction {
    static selector = ".s_ai_livechat";

    setup() {
        this.renderAt("ai_website_livechat.s_ai_livechat_edit", {
            livechatAvailable: this.livechatAvailable,
            fallbackButtonActive: this.fallbackButtonActive,
            fallbackButtonURL: this.el.dataset.fallbackButtonURL,
            fallbackButtonText: this.el.dataset.fallbackButtonText || _t('Contact Us'),
        }, this.el.querySelector(".ai_livechat_component"))
        this.el.querySelector('.ai_livechat_prompt_textarea').setAttribute('placeholder', this.el.dataset.promptPlaceholder || _t('Ask AI'));
    }
    get livechatAvailable() {
        return this.el.dataset.livechatChannelId;
    }
    get fallbackButtonActive() {
        return !this.livechatAvailable &&
        this.el.dataset.hasFallbackButton === "true" &&
        Boolean(this.el.dataset.fallbackButtonURL);
    }
}

registry.category("public.interactions.edit").add("ai_website_livechat.ai_livechat_edit", {
    Interaction: AILivechatEdit,
});
