import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";


class IprDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            total: 0,
            pending: 0,
            approved: 0,
            rejected: 0,
            draft: 0,
        });
        onWillStart(async () => {
            const data = await this.orm.call("ipr.request", "get_dashboard_data", []);
            Object.assign(this.state, data);
        });
    }

    openRequests(state) {
        const domain = state ? [["state", "=", state]] : [];
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Purchase Requests",
            res_model: "ipr.request",
            views: [[false, "tree"], [false, "kanban"], [false, "form"]],
            domain,
        });
    }
}

IprDashboard.template = "sonha_ipr.IprDashboard";

registry.category("actions").add("sonha_ipr.dashboard", IprDashboard);

