/** @odoo-module */
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export default class SystrayAction extends Component {
    static props = {};
    static template = "ai.SystrayAction";

    setup() {
        super.setup();
        this.aiChatLauncher = useService("aiChatLauncher");
        this.actionService = useService("action");
        this.mailStore = useService("mail.store");
        this.bus = this.env.bus;
    }

    async onClickLaunchAIChat() {
        const currentController = this.actionService.currentController;
        const model = await this.getCurrentViewInfo();
        if (currentController?.view?.type === "form" && model.root.fields?.message_ids) {
            if (!model) {
                return;
            }

            // Force save the record so we can fetch chatter messages from the back - end
            const saved = await model.root.save();
            if (!saved) {
                return;
            }

            const composerAction = {
                type: "ir.actions.act_window",
                view_mode: "form",
                res_model: "mail.compose.message",
                views: [[false, "form"]],
                target: "new",
                view_id: false,
                context: {
                    default_model: model.root.resModel,
                    default_res_ids: [model.root.resId],
                    clicked_on_full_composer: true,
                },
            };
            const thread = await this.mailStore.Thread.getOrFetch({
                model: model.root.resModel,
                id: model.root.resId,
            });
            await this.aiChatLauncher.launchAIChat({
                callerComponentName: "chatter_ai_button",
                recordModel: model.root.resModel,
                recordId: model.root.resId,
                originalRecordData: model.root.data,
                originalRecordFields: model.root.fields,
                aiChatSourceId: model.root.resId,
                aiSpecialActions: {
                    sendMessage: (content) => {
                        composerAction["name"] = _t("Send Message");
                        composerAction["context"]["default_subtype_xmlid"] = "mail.mt_comment";
                        composerAction["context"]["default_body"] = content;
                        this.actionService.doAction(composerAction, {
                            onClose: () => thread?.fetchNewMessages(),
                        });
                    },
                    logNote: (content) => {
                        composerAction["name"] = _t("Log Note");
                        composerAction["context"]["default_subtype_xmlid"] = "mail.mt_note";
                        composerAction["context"]["default_body"] = content;
                        this.actionService.doAction(composerAction, {
                            onClose: () => thread?.fetchNewMessages(),
                        });
                    },
                },
                channelTitle: model.root.data.display_name,
            });
        } else {
            await this.aiChatLauncher.launchAIChat({
                callerComponentName: "systray_ai_button",
            });
        }
    }

    async getCurrentViewInfo() {
        return new Promise((resolve) => {
            const listener = ({ detail }) => {
                this.bus.removeEventListener("AI.SEND_MODEL_DETAILS", listener);
                clearTimeout(timeout);
                resolve(detail);
            };
            const timeout = setTimeout(() => {
                this.bus.removeEventListener("AI.SEND_MODEL_DETAILS", listener);
                resolve(null);
            }, 100); // Timeout to avoid waiting indefinitely
            this.bus.addEventListener("AI.SEND_MODEL_DETAILS", listener);
            this.bus.trigger("AI.REQUEST_MODEL_DETAILS");
        });
    }
}

registry
    .category("systray")
    .add("ai.systray_action", { Component: SystrayAction }, { sequence: 30 });
