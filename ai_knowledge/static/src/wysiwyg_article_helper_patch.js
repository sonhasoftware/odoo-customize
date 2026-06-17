import { WysiwygArticleHelper } from "@knowledge/components/wysiwyg_article_helper/wysiwyg_article_helper";

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

patch(WysiwygArticleHelper.prototype, {
    setup(){
        super.setup();
        this.aiChatLauncher = useService("aiChatLauncher");
    },
    async onGenerateArticleClick() {
        await this.aiChatLauncher.launchAIChat({
            callerComponentName: "html_field_knowledge",
            recordModel: "knowledge.article",
            recordId: this.props.record.resId,
            aiSpecialActions: {
                insert: (fragment) => {
                    const generatedContentTitle = fragment.querySelector("h1,h2");
                    const articleTitle = this.props.editor.document.createElement("h1");
                    if (generatedContentTitle && generatedContentTitle.tagName !== "H1") {
                        articleTitle.innerText = generatedContentTitle.innerText;
                        generatedContentTitle.replaceWith(articleTitle);
                    } else if (!generatedContentTitle) {
                        const br = this.props.editor.document.createElement("BR");
                        articleTitle.replaceChildren(br);
                        fragment.prepend(articleTitle);
                    }
                    this.props.editor.editable.replaceChildren(...fragment.children);
                    this.props.editor.shared.selection.setCursorEnd(this.props.editor.editable);
                    this.props.editor.shared.history.addStep();
                },
            },
            aiChatSourceId: this.props.record.resId,
            channelTitle: _t("Knowledge Article Editor"),
        });
    }
});
