import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { rpc } from "@web/core/network/rpc";
import { useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { AddPageConfirmDialog } from "@website/components/dialog/add_page_dialog";

patch(AddPageConfirmDialog.prototype, {
    setup() {
        super.setup();
        this.notification = useService("notification");
        this.state = useState({
            ...this.state,
            instructions: "",
            tone: "",
            generateText: false,
            loading: false,
        });

        this.tones = {
            concise: {
                title: _t("Concise"),
                description: "Keep it short and to the point",
            },
            professional: {
                title: _t("Professional"),
                description: "Use a formal, professional tone",
            },
            friendly: {
                title: _t("Friendly"),
                description: "Keep it relaxed and easygoing",
            },
            persuasive: {
                title: _t("Persuasive"),
                description: "Make it more action-oriented",
            },
            informative: {
                title: _t("Informative"),
                description: "Make it clear and explanatory",
            },
        };
    },

    onChangeGenerateText(value) {
        this.state.generateText = value;
    },

    onToneSelect(ev) {
        const tone = ev.target.dataset.tone;
        if (tone === this.state.tone) {
            this.state.tone = "";
            return;
        }
        this.state.tone = tone;
    },

    get buttonTitle() {
        if (this.state.generateText) {
            return _t("Create with AI");
        }
        return _t("Create");
    },

    async processSectionsArch() {
        if (this.state.sectionsArch) {
            const aiGeneratedContent = await rpc('/ai_website/generate_page', {
                instructions: this.state.instructions || "",
                name: this.state.name,
                sectionsArch: this.state.sectionsArch,
                tone: this.state.tone ? this.tones[this.state.tone] : "",
                templateId: this.state.templateId || "",
            });
            if (aiGeneratedContent && aiGeneratedContent.html) {
                if (aiGeneratedContent.error) {
                    this.notification.add(aiGeneratedContent.error, {
                        type: "danger",
                        sticky: true,
                    });
                    return false;
                }
                this.state.sectionsArch = aiGeneratedContent.html;
            }
        }
    },

    async addPage() {
        if (this.state.generateText) {
            this.state.loading = true;
            await this.processSectionsArch();
        }
        await super.addPage();
        this.state.loading = false;
    },
});
