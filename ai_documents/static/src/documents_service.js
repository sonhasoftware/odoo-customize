import { DocumentService } from "@documents/core/document_service";
import { markup } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";

patch(DocumentService.prototype, {
    async start() {
        await super.start(...arguments);
        this.busService.subscribe(
            "ai_documents.auto_sort_notification",
            ({ message, type, document_name, document_access_url }) => {
                const link = markup`<a href="${document_access_url}?documents_init_open_preview=">${document_name}</a>`;
                this.notification.add(
                    markup`<img class="mb-1 me-2" src="/ai/static/description/icon.png" height="20" width="20"/>${link} - ${message}`,
                    {
                        type: type,
                        autocloseDelay: 10000,
                    }
                );
            }
        );
        this.busService.start();
    },
});
