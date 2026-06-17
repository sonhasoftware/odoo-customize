import { patch } from "@web/core/utils/patch";
import { DocumentsActivityController } from "@documents/views/activity/documents_activity_controller";
import { AiDocumentsControllerMixin } from "../documents_controller_mixin";

patch(DocumentsActivityController.prototype, AiDocumentsControllerMixin());
