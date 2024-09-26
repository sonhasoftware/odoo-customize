/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
export class CopyListController extends ListController {
   setup() {
       super.setup();
   }
   OnTestClick() {
       this.actionService.doAction({
          type: 'ir.actions.act_window',
          res_model: 'copy',
          name:'Open Wizard',
          view_mode: 'form',
          view_type: 'form',
          views: [[false, 'form']],
          target: 'new',
      });
   }
}
registry.category("views").add("button_in_tree", {
   ...listView,
   Controller: CopyListController,
   buttonTemplate: "button_copy.ListView.Buttons",
});
