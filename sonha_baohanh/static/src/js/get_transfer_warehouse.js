/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
export class GetTransferController extends ListController {
   setup() {
       super.setup();
   }
   GetData() {
        this.actionService.doAction({
          type: 'ir.actions.act_window',
          res_model: 'get.transfer.warehouse',
          name:'Open Transfer Wizard',
          view_mode: 'form',
          view_type: 'form',
          views: [[false, 'form']],
          target: 'new',
      });
   }
}
registry.category("views").add("button_transfer", {
   ...listView,
   Controller: GetTransferController,
   buttonTemplate: "button_get_data.ListView.Buttons",
});