import { patch } from "@web/core/utils/patch";
import { DocumentsKanbanController } from "@documents/views/kanban/documents_kanban_controller";
import { AiDocumentsControllerMixin } from "../documents_controller_mixin";

patch(DocumentsKanbanController.prototype, AiDocumentsControllerMixin());
