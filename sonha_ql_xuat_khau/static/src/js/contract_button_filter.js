/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
export class FilterContractListController extends ListController {
   setup() {
       super.setup();
   }
   FilterClick() {
            this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "popup.contract.filter.list",
            name: "Filter",
            views: [[false, "form"]],
            target: "new",
            context: {
                active_model: this.props.resModel,
            },
        });
   }
}
registry.category("views").add("contract_filter_button_tree", {
   ...listView,
   Controller: FilterContractListController,
   buttonTemplate: "button_filter.ListView.Buttons",
});
