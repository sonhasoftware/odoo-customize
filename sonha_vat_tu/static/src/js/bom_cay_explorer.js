/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

function rpcErrorMessage(error) {
    if (!error) {
        return _t("Đã xảy ra lỗi khi gọi máy chủ.");
    }
    const data = error.data || {};
    if (data.arguments && data.arguments.length) {
        return String(data.arguments[0]);
    }
    if (data.message) {
        return String(data.message);
    }
    return error.message || String(error);
}

function isBusinessRpcError(error) {
    const name = error?.exceptionName || error?.data?.name || "";
    return (
        name.includes("UserError") ||
        name.includes("ValidationError") ||
        name.includes("MissingError") ||
        name.includes("AccessError")
    );
}

export class BomCayExplorerAction extends Component {
    static template = "sonha_vat_tu.BomCayExplorer";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            periodId: false,
            periods: [],
            maTpGoc: "",
            maList: [],
            thangTu: "",
            thangDen: "",
            loading: false,
            loaded: false,
            header: {},
            treeLines: [],
            nvlTable: [],
            visibleMonths: [],
            stats: {},
        });
        onWillStart(async () => {
            const periods = await this.orm.searchRead(
                "ke.hoach.vat.tu",
                [
                    [
                        "state",
                        "in",
                        ["tinh_toan", "tong_hop", "dat_hang", "bcu_tong_hop", "phe_duyet"],
                    ],
                ],
                ["id", "display_name", "code"],
                { order: "period_month desc, id desc", limit: 80 },
            );
            this.state.periods = periods;
            if (periods.length) {
                await this.onPeriodChange(periods[0].id);
            }
        });
    }

    async onPeriodChange(periodId) {
        const pid = parseInt(periodId, 10);
        if (!pid) {
            return;
        }
        this.state.periodId = pid;
        this.state.loaded = false;
        try {
            const info = await this.orm.call("bom.cay.explorer", "get_period_info", [pid]);
            this.state.maList = info.ma_list || [];
            this.state.thangTu = info.thang_tu || "";
            this.state.thangDen = info.thang_den || "";
            if (!this.state.maTpGoc && this.state.maList.length) {
                this.state.maTpGoc = this.state.maList[0].ma;
            }
        } catch (e) {
            this._notifyRpcError(e);
        }
    }

    _notifyRpcError(error) {
        const msg = rpcErrorMessage(error);
        const business = isBusinessRpcError(error);
        this.notification.add(msg, {
            type: business ? "warning" : "danger",
            title: business ? _t("Không tra cứu được") : _t("Lỗi hệ thống"),
        });
    }

    formatNum(val, digits = 3) {
        const n = Number(val) || 0;
        return n.toLocaleString(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: digits,
        });
    }

    monthQty(row, offset, field) {
        const m = row.months && row.months[String(offset)];
        if (!m) {
            return this.formatNum(0, field === "qty_kh" ? 2 : 3);
        }
        return this.formatNum(m[field], field === "qty_kh" ? 2 : 3);
    }

    async loadTree() {
        if (!this.state.periodId || !this.state.maTpGoc) {
            this.notification.add(_t("Chọn kỳ và mã TP gốc."), { type: "warning" });
            return;
        }
        this.state.loading = true;
        try {
            const data = await this.orm.call("bom.cay.explorer", "load_explorer", [
                this.state.periodId,
                this.state.maTpGoc.trim(),
                this.state.thangTu,
                this.state.thangDen,
            ]);
            this.state.header = {
                title: `${data.ma_tp_goc} — ${data.ten_tp_goc || ""}`,
                chiNhanh: data.chi_nhanh,
                range: data.range_label,
            };
            this.state.header.ma = data.ma_tp_goc;
            this.state.header.ten = data.ten_tp_goc || "";
            this.state.treeLines = data.tree_lines || [];
            this.state.nvlTable = data.nvl_table || [];
            this.state.visibleMonths = data.visible_months || [];
            this.state.stats = data.stats || {};
            this.state.loaded = true;
        } catch (e) {
            this._notifyRpcError(e);
            this.state.loaded = false;
            this.state.treeLines = [];
            this.state.nvlTable = [];
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("actions").add("bom_cay_explorer", BomCayExplorerAction);
