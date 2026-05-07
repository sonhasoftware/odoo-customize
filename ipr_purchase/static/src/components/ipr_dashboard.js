/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class IprDashboard extends Component {
    static template = "ipr_purchase.IprDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            loading: true,
            stats: {
                total: 0,
                draft: 0,
                confirm: 0,
                approve: 0,
                reject: 0,
            },
        });

        onWillStart(async () => {
            await this._loadStats();
        });
    }

    async _loadStats() {
        this.state.loading = true;
        try {
            const records = await this.orm.searchRead(
                "ipr.request",
                [],
                ["state"],
                { limit: 0 }
            );
            const stats = { total: records.length, draft: 0, confirm: 0, approve: 0, reject: 0 };
            for (const r of records) {
                if (r.state in stats) stats[r.state]++;
            }
            this.state.stats = stats;
        } catch (e) {
            console.error("IPR Dashboard load error:", e);
        } finally {
            this.state.loading = false;
        }
    }

    openAll() { this._openRequests(false); }
    openDraft() { this._openRequests("draft"); }
    openConfirm() { this._openRequests("confirm"); }
    openApprove() { this._openRequests("approve"); }
    openReject() { this._openRequests("reject"); }

    _openRequests(state) {
        const domain = state ? [["state", "=", state]] : [];
        this.action.doAction({
            name: "Phiếu yêu cầu mua hàng",
            type: "ir.actions.act_window",
            res_model: "ipr.request",
            view_mode: "tree,form",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    async refresh() {
        await this._loadStats();
    }
}

registry.category("actions").add("ipr_dashboard_action", IprDashboard);