import { Interaction } from "@web/public/interaction";
import { registry } from "@web/core/registry";
import { AILivechatComponent } from "@ai_website_livechat/website/components/ai_livechat_component/ai_livechat";
import { _t } from "@web/core/l10n/translation";


export class AILivechat extends Interaction {
    static selector = ".s_ai_livechat";
    dynamicContent = {
        ".ai_livechat_component": {
            "t-component": () => {
                return [
                    AILivechatComponent, 
                    {
                        'chatStyle': this.el.dataset.chatStyle ? this.el.dataset.chatStyle : 'fullscreen',
                        'agentId': parseInt(this.el.dataset.agentId),
                        'livechatChannelId': parseInt(this.el.dataset.livechatChannelId),
                        'promptPlaceholder':  this.el.dataset.promptPlaceholder ? this.el.dataset.promptPlaceholder : _t('Ask AI'),
                        'hasFallbackButton':  this.el.dataset.hasFallbackButton === 'true' ? true : false,
                        'fallbackButtonText':  this.el.dataset.fallbackButtonText ? this.el.dataset.fallbackButtonText : _t('Contact Us'),
                        'fallbackButtonURL':  this.el.dataset.fallbackButtonURL,
                    }
                ]
            }
        }
    };
}

registry.category("public.interactions").add("ai_website_livechat.ai_livechat", AILivechat);
