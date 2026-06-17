import { _t } from "@web/core/l10n/translation";

export const AiDocumentsControllerMixin = () => ({
    async onClickAutoSort() {
        const documentsIds = this.aiSortableDocuments().map((r) => r.data.id);
        const action = await this.orm.call("documents.document", "action_ai_sort", [documentsIds]);
        if (action) {
            this.actionService.doAction(action);
        }
        this.documentService.reload();
    },

    aiSortableDocuments() {
        return this.model.targetRecords.filter((r) => r.data.ai_sortable);
    },

    getTopBarActionMenuItems() {
        const menuItems = super.getTopBarActionMenuItems();
        return {
            ...menuItems,
            aiAutoSort: {
                isAvailable: () =>
                    this.env.searchModel.getSelectedFolder()?.ai_sort_prompt &&
                    this.aiSortableDocuments().length,
                sequence: 55,
                description: _t("Sort With AI"),
                callback: async () => this.onClickAutoSort(),
                groupNumber: 1,
            },
        };
    },
});
