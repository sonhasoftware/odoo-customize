/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formatFloat } from "@web/views/fields/formatters";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { useEffect } from "@odoo/owl";
import { ListRenderer } from "@web/views/list/list_renderer";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

// ---------------------------------------------------------------------------
// Tháng kỳ (dùng chung)
// ---------------------------------------------------------------------------

function getMonthText(periodMonth, offset) {
    if (!periodMonth) {
        return "";
    }
    const parts = periodMonth.split("/");
    if (parts.length !== 2) {
        return "";
    }
    let month = parseInt(parts[0], 10);
    let year = parseInt(parts[1], 10);
    if (Number.isNaN(month) || Number.isNaN(year)) {
        return "";
    }
    month += offset;
    while (month > 12) {
        month -= 12;
        year += 1;
    }
    return `${String(month).padStart(2, "0")}/${year}`;
}

const PERIOD_MONTH_PARENT_MODELS = new Set([
    "ke.hoach.vat.tu",
    "ke.hoach.kinh.doanh",
]);

function getPeriodMonth(list) {
    const parent = list && list._parent;
    if (parent && PERIOD_MONTH_PARENT_MODELS.has(parent.resModel) && parent.data) {
        return parent.data.period_month || "";
    }
    try {
        const root = list && list.model && list.model.root;
        if (root && PERIOD_MONTH_PARENT_MODELS.has(root.resModel) && root.data) {
            return root.data.period_month || "";
        }
    } catch (e) {
        // ignore
    }
    try {
        for (const rec of list?.records || []) {
            if (rec.data?.period_month) {
                return rec.data.period_month;
            }
        }
    } catch (e) {
        // ignore
    }
    return "";
}

function isMonthKeyInRange(monthKey, fromKey, toKey) {
    if (!fromKey || !toKey) {
        return true;
    }
    const parse = (key) => {
        if (!key) {
            return null;
        }
        const parts = key.split("/");
        if (parts.length !== 2) {
            return null;
        }
        const month = parseInt(parts[0], 10);
        const year = parseInt(parts[1], 10);
        if (Number.isNaN(month) || Number.isNaN(year)) {
            return null;
        }
        return year * 12 + month;
    };
    const value = parse(monthKey);
    const fromValue = parse(fromKey);
    const toValue = parse(toKey);
    if (value === null || fromValue === null || toValue === null) {
        return true;
    }
    return value >= fromValue && value <= toValue;
}

// ---------------------------------------------------------------------------
// 1) Label động cột tháng (list thường trong form kỳ)
// ---------------------------------------------------------------------------

const MONTH_FIELD_LABELS = (() => {
    const labels = {};
    const simple = ["qty_t", "qty_kd_t", "qty_sx_t", "qty_cl_t"];
    const prefixed = {
        ton_dau_t: "Tồn đầu",
        ve_du_kien_don_vi_t: "Hàng đi đường",
        vt_can_dung_t: "Cần dùng",
        ton_cuoi_t: "Tồn cuối",
        so_luong_du_phong_t: "Dự phòng",
        so_luong_thieu_t: "Thiếu",
        so_luong_can_mua_t: "Cần mua",
        tong_ton_nvl_sl_t: "Tồn NVL",
        tong_hang_di_duong_sl_t: "Đi đường đơn vị",
        tong_sl_vt_can_dung_t: "Vật tư cần dùng",
        sl_du_tru_toi_thieu_t: "Dự trữ tối thiểu",
        sl_can_mua_theo_moq_t: "SL cần mua dựa theo MOQ NCC",
        sl_dat_mua_de_xuat_t: "Đặt mua đề xuất",
        sl_dat_mua_chot_t: "Đặt mua chốt",
        sl_ton_kho_t: "Tồn sau mua",
        so_ngay_vong_quay_ton_t: "Ngày vòng quay tồn",
        gia_tri_ton_kho_t: "Giá trị tồn kho",
    };
    for (let offset = 0; offset < 4; offset++) {
        for (const p of simple) {
            labels[`${p}${offset}`] = { offset, prefix: "" };
        }
        for (const [p, prefix] of Object.entries(prefixed)) {
            labels[`${p}${offset}`] = { offset, prefix };
        }
    }
    return labels;
})();

patch(ListRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        useEffect(
            () => {
                const columns = this.props?.archInfo?.columns;
                if (!columns?.some((col) => col.type === "field" && MONTH_FIELD_LABELS[col.name])) {
                    return;
                }
                const periodMonth = getPeriodMonth(this.props.list);
                if (!periodMonth) {
                    return;
                }
                this.allColumns = this.processAllColumn(columns, this.props.list);
                this.state.columns = this.getActiveColumns(this.props.list);
            },
            () => [getPeriodMonth(this.props.list), this.props.list?.records?.length],
        );
    },

    processAllColumn(allColumns, list) {
        const result = super.processAllColumn(allColumns, list);
        const periodMonth = getPeriodMonth(list);
        if (!periodMonth) {
            return result;
        }
        return result.map((col) => {
            const cfg = col.type === "field" ? MONTH_FIELD_LABELS[col.name] : undefined;
            if (!cfg) {
                return col;
            }
            const monthText = getMonthText(periodMonth, cfg.offset);
            if (!monthText) {
                return col;
            }
            const label = cfg.prefix ? `${cfg.prefix} ${monthText}` : `Tháng ${monthText}`;
            return { ...col, label };
        });
    },
});

// ---------------------------------------------------------------------------
// 2) Header merge 2 tầng (B4 / B5)
// ---------------------------------------------------------------------------

const B4_PREFIX = {
    ve_du_kien_don_vi_t: "Hàng đi đường",
    vt_can_dung_t: "Cần dùng",
    ton_cuoi_t: "Tồn cuối",
};

const NHU_CAU_PREFIX = {
    so_luong_t: "Sản lượng vật tư cần dùng (Kg)",
};

function getMonthlyMergeInfo(fieldName, prefixMap) {
    if (!fieldName) {
        return null;
    }
    const prefixes = Object.entries(prefixMap).sort(
        ([a], [b]) => b.length - a.length
    );
    for (const [prefix, categoryLabel] of prefixes) {
        if (!fieldName.startsWith(prefix)) {
            continue;
        }
        const suffix = fieldName.slice(prefix.length);
        if (["0", "1", "2", "3"].includes(suffix)) {
            return { prefix, categoryLabel, offset: parseInt(suffix, 10) };
        }
    }
    return null;
}

class VatTuMergedHeaderRenderer extends ListRenderer {
    static template = "sonha_vat_tu.VatTuMergedHeaderRenderer";

    onClickSortColumn(column) {
        if (!column?.name) {
            return;
        }
        return super.onClickSortColumn(column);
    }

    _headerTh(col, index) {
        const columnOffset = this.hasSelectors ? 2 : 1;
        if (col?.name) {
            const byName = this.tableRef.el.querySelector(`th[data-name="${col.name}"]`);
            if (byName) {
                return byName;
            }
        }
        return this.tableRef.el.querySelector(`thead tr:first-child th:nth-child(${index + columnOffset})`);
    }

    setDefaultColumnWidths() {
        const widths = this.state.columns.map((col) => this.calculateColumnWidth(col));
        const sumRel = widths.filter(({ type }) => type === "relative").reduce((s, { value }) => s + value, 0);
        widths.forEach(({ type, value }, i) => {
            const el = this._headerTh(this.state.columns[i], i);
            if (!el) {
                return;
            }
            if (type === "absolute") {
                el.style[this.isEmpty ? "width" : "minWidth"] = value;
            } else if (type === "relative" && this.isEmpty) {
                el.style.width = `${((value / sumRel) * 100).toFixed(2)}%`;
            }
        });
    }

    freezeColumnWidths() {
        const className = this.props.archInfo?.className || "";
        if (className.split(/\s+/).filter(Boolean).includes("sh_free_width_tree")) {
            if (this.keepColumnWidths || this.editedRecord) {
                return super.freezeColumnWidths(...arguments);
            }
            const table = this.tableRef.el;
            if (table) {
                table.style.tableLayout = "auto";
                table.style.width = null;
                table.querySelectorAll("thead th, tbody td, tfoot td").forEach((cell) => {
                    cell.style.width = null;
                    cell.style.minWidth = null;
                    cell.style.maxWidth = null;
                });
            }
            return;
        }
        if (!this.keepColumnWidths) {
            this.columnWidths = null;
        }
        const table = this.tableRef.el;
        if (!this.columnWidths?.length) {
            table.style.tableLayout = "auto";
            if (this.rootWidthFixed) {
                this.rootRef.el.style.width = null;
            }
            table.style.width = null;
            table.querySelectorAll("thead th").forEach((th) => {
                th.style.width = null;
                th.style.maxWidth = null;
            });
            this.setDefaultColumnWidths();
            this.columnWidths = this.computeColumnWidthsFromContent();
            table.style.tableLayout = "fixed";
        }
        this.state.columns.forEach((col, index) => {
            const th = this._headerTh(col, index);
            const w = this.columnWidths[index];
            if (th && w !== undefined && !th.style.width) {
                th.style.width = `${Math.floor(w)}px`;
            }
        });
    }

    computeColumnWidthsFromContent() {
        const table = this.tableRef.el;
        table.classList.add("o_list_computing_widths");
        const leafThs = this.state.columns.map((col, i) => this._headerTh(col, i)).filter(Boolean);
        const widths = leafThs.map((th) => th.getBoundingClientRect().width);
        const getW = (th) => {
            const i = leafThs.indexOf(th);
            return i !== -1 ? widths[i] : 0;
        };
        const shrink = (ths, amount) => {
            let ok = true;
            for (const th of ths) {
                const i = leafThs.indexOf(th);
                if (i === -1) {
                    continue;
                }
                let max = widths[i] - amount;
                if (max < 92) {
                    max = 92;
                    ok = false;
                }
                th.style.maxWidth = `${Math.floor(max)}px`;
                widths[i] = max;
            }
            return ok;
        };
        const sorted = leafThs
            .filter((th) => th && !th.classList.contains("o_list_button"))
            .sort((a, b) => getW(b) - getW(a));
        const allowed = table.parentNode.getBoundingClientRect().width;
        let total = widths.reduce((s, w) => s + w, 0);
        for (let n = 1; total > allowed; n++) {
            const cols = sorted.slice(0, n);
            const cur = getW(cols[0]);
            for (; sorted[n] && cur === getW(sorted[n]); n++) {
                cols.push(sorted[n]);
            }
            const next = sorted[n];
            const remove = Math.ceil((total - allowed) / cols.length);
            const amount = Math.min(remove, cur - (next ? getW(next) : 0));
            if (!shrink(cols, amount)) {
                break;
            }
            total = widths.reduce((s, w) => s + w, 0);
        }
        table.classList.remove("o_list_computing_widths");
        return widths;
    }

    _buildColumnGroups(getMergeInfo, groupIdPrefix) {
        const groups = [];
        let current = null;
        for (const col of this.state.columns || []) {
            if (col.type !== "field") {
                groups.push({ id: col.name || col.type, label: "", span: 1, rowspan: 2, column: col });
                current = null;
                continue;
            }
            const info = getMergeInfo(col.name);
            if (!info) {
                groups.push({ id: col.name, label: col.label, span: 1, rowspan: 2, column: col });
                current = null;
                continue;
            }
            if (!current || current.label !== info.categoryLabel) {
                current = {
                    id: `${groupIdPrefix}_${info.prefix}_${groups.length}`,
                    label: info.categoryLabel,
                    span: 1,
                    rowspan: 1,
                    column: col,
                };
                groups.push(current);
            } else {
                current.span += 1;
            }
        }
        return groups;
    }

    _buildMergeColumns(getMergeInfo, labelFn) {
        const periodMonth = getPeriodMonth(this.props.list);
        const out = [];
        for (const col of this.state.columns || []) {
            const info = getMergeInfo(col.name);
            if (info) {
                out.push({ ...col, label: labelFn(periodMonth, info) });
            }
        }
        return out;
    }
}

function labelThang(periodMonth, info) {
    const t = getMonthText(periodMonth, info.offset);
    return t ? `Tháng ${t}` : `T${info.offset}`;
}

class VatTuMergedB4HeaderRenderer extends VatTuMergedHeaderRenderer {
    getColumnGroups() {
        return this._buildColumnGroups((n) => getMonthlyMergeInfo(n, B4_PREFIX), "b4");
    }

    getMergeColumns() {
        return this._buildMergeColumns(
            (n) => getMonthlyMergeInfoWithField(n, B4_PREFIX),
            labelThang,
        );
    }
}

class VatTuMergedB5HeaderRenderer extends VatTuMergedHeaderRenderer {
    static template = "sonha_vat_tu.VatTuMergedB5HeaderRenderer";

    get mergedHeaderDepth() {
        return 3;
    }

    _parseMonthlyField(fieldName) {
        if (!fieldName) {
            return null;
        }
        if (fieldName.startsWith("tong_sl_vt_can_dung_t")) {
            const suffix = fieldName.slice("tong_sl_vt_can_dung_t".length);
            if (["0", "1", "2", "3"].includes(suffix)) {
                return {
                    block: "can_dung",
                    topLabel: "Cần dùng",
                    offset: parseInt(suffix, 10),
                    fieldName,
                };
            }
        }
        if (fieldName.startsWith("tong_hang_di_duong_sl_t")) {
            const suffix = fieldName.slice("tong_hang_di_duong_sl_t".length);
            if (["0", "1", "2", "3"].includes(suffix)) {
                return {
                    block: "di_duong",
                    topLabel: "Đi đường đơn vị",
                    offset: parseInt(suffix, 10),
                    fieldName,
                };
            }
        }
        return null;
    }

    _isTripletBlock(info) {
        return false;
    }

    getTopRowGroups() {
        const groups = [];
        let current = null;
        for (const col of this.state.columns || []) {
            if (col.type !== "field") {
                groups.push({
                    id: col.name || col.type,
                    label: "",
                    span: 1,
                    rowspan: this.mergedHeaderDepth,
                    column: col,
                });
                current = null;
                continue;
            }
            const info = this._parseMonthlyField(col.name);
            if (!info) {
                groups.push({
                    id: col.name,
                    label: col.label,
                    span: 1,
                    rowspan: this.mergedHeaderDepth,
                    column: col,
                });
                current = null;
                continue;
            }
            if (!current || current.label !== info.topLabel) {
                current = {
                    id: `merged_top_${info.block}_${groups.length}`,
                    label: info.topLabel,
                    span: 1,
                    rowspan: 1,
                    column: col,
                };
                groups.push(current);
            } else {
                current.span += 1;
            }
        }
        return groups;
    }

    getMidRowGroups() {
        const periodMonth = getPeriodMonth(this.props.list);
        const groups = [];
        for (const col of this.state.columns || []) {
            const info = this._parseMonthlyField(col.name);
            if (!info) {
                continue;
            }
            if (info.block === "can_dung" || info.block === "di_duong") {
                groups.push({
                    id: `merged_mid_${info.block}_${info.offset}`,
                    label: labelThang(periodMonth, info),
                    span: 1,
                    rowspan: 2,
                    column: col,
                });
            } else if (this._isTripletBlock(info) && info.kind === "sl") {
                groups.push({
                    id: `merged_mid_${info.block}_${info.offset}`,
                    label: labelThang(periodMonth, info),
                    span: 3,
                    rowspan: 1,
                    column: col,
                });
            }
        }
        return groups;
    }

    getLeafMergeColumns() {
        const periodMonth = getPeriodMonth(this.props.list);
        const out = [];
        for (const col of this.state.columns || []) {
            const info = this._parseMonthlyField(col.name);
            if (info && this._isTripletBlock(info)) {
                out.push({
                    ...col,
                    label: labelThangSub(periodMonth, info),
                });
            }
        }
        return out;
    }
}

class VatTuMergedB6HeaderRenderer extends VatTuMergedB5HeaderRenderer {
    _parseMonthlyField(fieldName) {
        const info = super._parseMonthlyField(fieldName);
        if (info) {
            return info;
        }
        if (/^ve_du_kien_bcu_t[0-3]$/.test(fieldName)) {
            return {
                block: "bcu_di_duong",
                kind: "sl",
                topLabel: "Đi đường BCU",
                offset: parseInt(fieldName.slice(-1), 10),
                fieldName,
            };
        }
        const bcuKinds = [
            ["dg", "ve_du_kien_bcu_dg_t"],
            ["gt", "ve_du_kien_bcu_gt_t"],
        ];
        for (const [kind, prefix] of bcuKinds) {
            if (fieldName.startsWith(prefix)) {
                const suffix = fieldName.slice(prefix.length);
                if (["0", "1", "2", "3"].includes(suffix)) {
                    return {
                        block: "bcu_di_duong",
                        kind,
                        topLabel: "Đi đường BCU",
                        offset: parseInt(suffix, 10),
                        fieldName,
                    };
                }
            }
        }
        return null;
    }

    _isTripletBlock(info) {
        return info && info.block === "bcu_di_duong";
    }
}

function labelThangSub(periodMonth, info) {
    if (info.kind === "dg") {
        return "Đơn giá";
    }
    if (info.kind === "gt") {
        return "Giá trị";
    }
    if (info.kind === "sl") {
        return "Số lượng";
    }
    const field = info.fieldName || "";
    if (field.includes("_don_gia_t") || field.includes("_dg_t")) {
        return "Đơn giá";
    }
    if (field.includes("_gia_tri_t") || field.includes("_gt_t")) {
        return "Giá trị";
    }
    if (field.includes("_don_vi_t") || field.includes("_sl_t")) {
        return "Số lượng";
    }
    const t = getMonthText(periodMonth, info.offset);
    return t ? `Tháng ${t}` : `T${info.offset}`;
}

function getMonthlyMergeInfoWithField(fieldName, prefixMap) {
    const info = getMonthlyMergeInfo(fieldName, prefixMap);
    if (info) {
        info.fieldName = fieldName;
    }
    return info;
}

function registerMergedView(key, Renderer) {
    registry.category("views").add(key, { ...listView, Renderer });
}

class VatTuBaoCaoListController extends ListController {
    static template = "sonha_vat_tu.VatTuBaoCaoListView";

    /** Chỉ bound server actions — bỏ Export/Archive/... mặc định của list view. */
    get baoCaoCogMenuItems() {
        const { actionMenus } = this.props.info;
        if (!actionMenus) {
            return { action: [], print: [] };
        }
        return {
            action: actionMenus.action || [],
            print: actionMenus.print || [],
        };
    }
}

function registerBaoCaoListView(key, Renderer, Controller = VatTuBaoCaoListController) {
    registry.category("views").add(key, {
        ...listView,
        Renderer,
        Controller,
    });
}

async function saveReportLineGhiChu(env, record, value) {
    const text = value ?? "";
    if ((record.data.ghi_chu || "") === text) {
        return;
    }
    await env.services.orm.write(record.resModel, [record.resId], { ghi_chu: text });
    record.data.ghi_chu = text;
}

function registerMergedOne2Many(key, Renderer) {
    class Field extends X2ManyField {}
    Field.components = { ...X2ManyField.components, ListRenderer: Renderer };
    registry.category("fields").add(key, {
        ...x2ManyField,
        component: Field,
        additionalClasses: [...(x2ManyField.additionalClasses || []), "o_field_one2many"],
    });
}

registerMergedView("vat_tu_merged_b4_list_view", VatTuMergedB4HeaderRenderer);
registerMergedView("vat_tu_merged_b5_list_view", VatTuMergedB5HeaderRenderer);
registerMergedOne2Many("vat_tu_merged_b4_one2many", VatTuMergedB4HeaderRenderer);
registerMergedOne2Many("vat_tu_merged_b5_one2many", VatTuMergedB5HeaderRenderer);
registerMergedOne2Many("vat_tu_merged_b6_one2many", VatTuMergedB6HeaderRenderer);
registerMergedOne2Many("vat_tu_b7_one2many", VatTuMergedB6HeaderRenderer);

// ---------------------------------------------------------------------------
// 4) B3 pivot: header Tháng × Đơn vị KD (dynamic)
// ---------------------------------------------------------------------------

const B3_FIXED_META = [
    { key: "ma_vat_tu", label: "Mã NVL" },
    { key: "ten_vat_tu", label: "Tên NVL" },
    { key: "don_vi_tinh", label: "ĐVT", m2o: true },
];

/** Cùng mã NVL nhiều tên → lấy tên dài nhất (khớp B4 gộp / SQL). */
function pickLongestText(current, candidate) {
    const cur = (current || "").trim();
    const next = (candidate || "").trim();
    if (!next) {
        return cur;
    }
    if (!cur || next.length > cur.length) {
        return next;
    }
    return cur;
}

function resolveKdCompanyCode(data, companyId) {
    const code = (data.don_vi_kd_code || "").trim();
    if (code) {
        return code;
    }
    const label = data.don_vi_kd_id && data.don_vi_kd_id[1];
    if (typeof label === "string" && label.trim()) {
        return label.trim();
    }
    return `#${companyId}`;
}

class VatTuB3PivotRenderer extends VatTuMergedHeaderRenderer {
    static template = "sonha_vat_tu.VatTuB3PivotRenderer";

    get displayOptionalFields() {
        return false;
    }

    get b3FixedMeta() {
        return B3_FIXED_META;
    }

    get kdCompanies() {
        const map = new Map();
        for (const rec of this.props.list.records) {
            const data = rec.data;
            const cid = data.don_vi_kd_id && data.don_vi_kd_id[0];
            if (!cid) {
                continue;
            }
            const code = resolveKdCompanyCode(data, cid);
            map.set(cid, code);
        }
        return [...map.entries()].sort((a, b) => String(a[1]).localeCompare(String(b[1])));
    }

    getPivotRows() {
        const byMat = new Map();
        for (const rec of this.props.list.records) {
            const d = rec.data;
            const key = d.ma_vat_tu || String(rec.resId);
            if (!byMat.has(key)) {
                byMat.set(key, { meta: d, byCompany: {} });
            } else {
                const row = byMat.get(key);
                row.meta = {
                    ...row.meta,
                    ten_vat_tu: pickLongestText(row.meta.ten_vat_tu, d.ten_vat_tu),
                };
            }
            const row = byMat.get(key);
            const cid = d.don_vi_kd_id && d.don_vi_kd_id[0];
            if (cid) {
                row.byCompany[cid] = d;
            }
        }
        return [...byMat.values()];
    }

    pivotQty(row, monthOffset, companyId) {
        const rec = row.byCompany[companyId];
        if (!rec) {
            return 0;
        }
        return rec[`qty_t${monthOffset}`] || 0;
    }

    pivotTotal(row, monthOffset) {
        let total = 0;
        for (const [cid] of this.kdCompanies) {
            total += this.pivotQty(row, monthOffset, cid);
        }
        return total;
    }

    formatQty(value) {
        return formatFloat(value || 0, { digits: [16, 3] });
    }

    formatMetaValue(row, meta) {
        const val = row.meta[meta.key];
        if (meta.m2o && Array.isArray(val)) {
            return val[1] || "";
        }
        if (meta.numeric) {
            return this.formatQty(val);
        }
        return val || "";
    }

    getColumnGroups() {
        const groups = [];
        for (const meta of B3_FIXED_META) {
            groups.push({
                id: `meta_${meta.key}`,
                label: meta.label,
                span: 1,
                rowspan: 2,
                column: null,
            });
        }
        const span = this.kdCompanies.length + 1;
        const periodMonth = getPeriodMonth(this.props.list);
        for (let t = 0; t < 4; t++) {
            const monthText = getMonthText(periodMonth, t) || `T${t}`;
            groups.push({
                id: `b3_month_${t}`,
                label: `Tháng ${monthText}`,
                span,
                rowspan: 1,
                column: null,
            });
        }
        return groups;
    }

    getQtySubColumns() {
        const out = [];
        for (let t = 0; t < 4; t++) {
            for (const [cid, code] of this.kdCompanies) {
                out.push({
                    id: `t${t}_c${cid}`,
                    label: code,
                    monthRef: t,
                    companyId: cid,
                    isTotal: false,
                });
            }
            out.push({
                id: `t${t}_total`,
                label: "Tổng",
                monthRef: t,
                companyId: null,
                isTotal: true,
            });
        }
        return out;
    }

    getMergeColumns() {
        return [];
    }
}

registerMergedOne2Many("vat_tu_b3_pivot_one2many", VatTuB3PivotRenderer);

// ---------------------------------------------------------------------------
// 3) Báo cáo nhu cầu: merge header + lọc cột theo tháng wizard
// ---------------------------------------------------------------------------

function getNhuCauThangFilter(list) {
    const ctx = list?.context || {};
    return { tu: ctx.nhu_cau_thang_tu || null, den: ctx.nhu_cau_thang_den || null };
}

function getVisibleMonthFields(list, recordData = null) {
    const filter = getNhuCauThangFilter(list);
    const periodMonth = recordData?.period_month || getPeriodMonth(list);
    if (!periodMonth) {
        return [];
    }
    if (!filter.tu || !filter.den) {
        return ["so_luong_t0", "so_luong_t1", "so_luong_t2", "so_luong_t3"];
    }
    const names = [];
    for (let offset = 0; offset < 4; offset++) {
        if (isMonthKeyInRange(getMonthText(periodMonth, offset), filter.tu, filter.den)) {
            names.push(`so_luong_t${offset}`);
        }
    }
    return names;
}

function getNhuCauRowTotal(recordData, list) {
    const fields = getVisibleMonthFields(list, recordData);
    if (!fields.length) {
        return recordData.tong_so_luong || 0;
    }
    return fields.reduce((acc, f) => acc + (recordData[f] || 0), 0);
}

function filterNhuCauColumns(columns, list) {
    const filter = getNhuCauThangFilter(list);
    if (!filter.tu || !filter.den) {
        return columns;
    }
    const periodMonth = getPeriodMonth(list);
    const getInfo = (n) => getMonthlyMergeInfo(n, NHU_CAU_PREFIX);
    if (!periodMonth) {
        return columns.filter((col) => col.type !== "field" || !getInfo(col.name));
    }
    return columns.filter((col) => {
        if (col.type !== "field" || col.name === "tong_so_luong") {
            return true;
        }
        const info = getInfo(col.name);
        if (!info) {
            return true;
        }
        return isMonthKeyInRange(getMonthText(periodMonth, info.offset), filter.tu, filter.den);
    });
}

class VatTuNhuCauHeaderRenderer extends VatTuMergedHeaderRenderer {
    get displayOptionalFields() {
        return false;
    }

    setup() {
        super.setup();
        useEffect(
            () => {
                this.allColumns = this.processAllColumn(this.props.archInfo.columns, this.props.list);
                this.state.columns = this.getActiveColumns(this.props.list);
            },
            () => {
                const f = getNhuCauThangFilter(this.props.list);
                return [this.props.list.records.length, getPeriodMonth(this.props.list), f.tu, f.den];
            }
        );
    }

    processAllColumn(allColumns, list) {
        return filterNhuCauColumns(super.processAllColumn(allColumns, list), list);
    }

    get aggregates() {
        const aggregates = super.aggregates;
        const filter = getNhuCauThangFilter(this.props.list);
        if (!filter.tu || !filter.den || this.props.list.isGrouped) {
            return aggregates;
        }
        const values = this.props.list.selection?.length
            ? this.props.list.selection.map((r) => r.data)
            : this.props.list.records.map((r) => r.data);
        if (!values.length) {
            return aggregates;
        }
        const total = values.reduce((acc, d) => acc + getNhuCauRowTotal(d, this.props.list), 0);
        const tongCol = this.allColumns.find((c) => c.name === "tong_so_luong");
        const digits = tongCol?.attrs?.digits ? JSON.parse(tongCol.attrs.digits) : undefined;
        aggregates.tong_so_luong = {
            help: tongCol?.attrs?.sum || _t("Tổng"),
            value: formatFloat(total, { digits }),
        };
        return aggregates;
    }

    getFormattedValue(column, record) {
        if (column.name === "tong_so_luong") {
            const filter = getNhuCauThangFilter(this.props.list);
            if (filter.tu && filter.den) {
                const digits = column.attrs?.digits ? JSON.parse(column.attrs.digits) : undefined;
                return formatFloat(getNhuCauRowTotal(record.data, this.props.list), { digits });
            }
        }
        return super.getFormattedValue(column, record);
    }

    getColumnGroups() {
        return this._buildColumnGroups((n) => getMonthlyMergeInfo(n, NHU_CAU_PREFIX), "nhu_cau");
    }

    getMergeColumns() {
        return this._buildMergeColumns(
            (n) => getMonthlyMergeInfo(n, NHU_CAU_PREFIX),
            (pm, info) => getMonthText(pm, info.offset) || `T${info.offset}`
        );
    }
}

registerMergedView("vat_tu_nhu_cau_list_view", VatTuNhuCauHeaderRenderer);

// ---------------------------------------------------------------------------
// 5) Báo cáo B3/B4 theo khoảng tháng lịch (wizard → line pivot)
// ---------------------------------------------------------------------------

function getBaoCaoMonthKeys(list) {
    const raw = (list?.context?.bao_cao_month_keys || "").trim();
    if (!raw) {
        return [];
    }
    return raw.split(",").map((s) => s.trim()).filter(Boolean);
}

class VatTuBaoCaoB3PivotRenderer extends VatTuB3PivotRenderer {
    getCalendarMonths() {
        return getBaoCaoMonthKeys(this.props.list);
    }

    getPivotRows() {
        const byMat = new Map();
        for (const rec of this.props.list.records) {
            const d = rec.data;
            const key = d.ma_vat_tu || String(rec.resId);
            if (!byMat.has(key)) {
                byMat.set(key, {
                    meta: {
                        ma_vat_tu: d.ma_vat_tu,
                        ten_vat_tu: d.ten_vat_tu,
                        don_vi_tinh: d.don_vi_tinh,
                    },
                    cells: {},
                });
            } else {
                const row = byMat.get(key);
                row.meta.ten_vat_tu = pickLongestText(row.meta.ten_vat_tu, d.ten_vat_tu);
            }
            const row = byMat.get(key);
            const cid = d.don_vi_kd_id && d.don_vi_kd_id[0];
            if (cid && d.month_key) {
                row.cells[`${d.month_key}|${cid}`] = d.qty || 0;
            }
        }
        return [...byMat.values()];
    }

    pivotQty(row, monthKey, companyId) {
        return row.cells[`${monthKey}|${companyId}`] || 0;
    }

    pivotTotal(row, monthKey) {
        let total = 0;
        for (const [cid] of this.kdCompanies) {
            total += this.pivotQty(row, monthKey, cid);
        }
        return total;
    }

    formatMetaValue(row, meta) {
        const val = row.meta[meta.key];
        if (meta.m2o && Array.isArray(val)) {
            return val[1] || "";
        }
        return val || "";
    }

    getColumnGroups() {
        const groups = [];
        for (const meta of B3_FIXED_META) {
            groups.push({
                id: `meta_${meta.key}`,
                label: meta.label,
                span: 1,
                rowspan: 2,
                column: null,
            });
        }
        const span = this.kdCompanies.length + 1;
        for (const monthKey of this.getCalendarMonths()) {
            groups.push({
                id: `b3_report_${monthKey}`,
                label: `Tháng ${monthKey}`,
                span,
                rowspan: 1,
                column: null,
            });
        }
        return groups;
    }

    getQtySubColumns() {
        const out = [];
        for (const monthKey of this.getCalendarMonths()) {
            for (const [cid, code] of this.kdCompanies) {
                out.push({
                    id: `${monthKey}_c${cid}`,
                    label: code,
                    monthRef: monthKey,
                    companyId: cid,
                    isTotal: false,
                });
            }
            out.push({
                id: `${monthKey}_total`,
                label: "Tổng",
                monthRef: monthKey,
                companyId: null,
                isTotal: true,
            });
        }
        return out;
    }
}

const BAO_CAO_B4_GROUPS = [
    { key: "ve_du_kien_don_vi", label: "Hàng đi đường" },
    { key: "vt_can_dung", label: "Cần dùng" },
    { key: "ton_cuoi", label: "Tồn cuối" },
];

const BAO_CAO_B4_META = [
    { key: "ma_sap", label: "Mã NVL" },
    { key: "ten_nvl", label: "Tên NVL" },
    { key: "chung_loai", label: "Chủng loại" },
    { key: "don_vi_tinh", label: "ĐVT", m2o: true },
    { key: "ton_dau", label: "Tồn đầu", numeric: true },
];

class VatTuBaoCaoB4PivotRenderer extends VatTuMergedHeaderRenderer {
    static template = "sonha_vat_tu.VatTuBaoCaoB4PivotRenderer";

    get BAO_CAO_B4_META() {
        return BAO_CAO_B4_META;
    }

    get displayOptionalFields() {
        return false;
    }

    getCalendarMonths() {
        return getBaoCaoMonthKeys(this.props.list);
    }

    getPivotRows() {
        const byMat = new Map();
        for (const rec of this.props.list.records) {
            const d = rec.data;
            const key = d.ma_sap || String(rec.resId);
            if (!byMat.has(key)) {
                byMat.set(key, {
                    meta: {
                        ma_sap: d.ma_sap,
                        ten_nvl: d.ten_nvl,
                        chung_loai: d.chung_loai,
                        don_vi_tinh: d.don_vi_tinh,
                        ton_dau: d.ton_dau,
                    },
                    months: {},
                });
            }
            if (d.month_key) {
                byMat.get(key).months[d.month_key] = d;
            }
        }
        return [...byMat.values()];
    }

    formatMetaValue(row, meta) {
        const val = row.meta[meta.key];
        if (meta.m2o && Array.isArray(val)) {
            return val[1] || "";
        }
        if (meta.numeric) {
            return this.formatQty(val);
        }
        return val || "";
    }

    formatQty(value) {
        return formatFloat(value || 0, { digits: [16, 3] });
    }

    metricValue(row, monthKey, field) {
        const rec = row.months[monthKey];
        if (!rec) {
            return 0;
        }
        const data = rec.data || rec;
        return data[field] || 0;
    }

    getColumnGroups() {
        const groups = [];
        for (const meta of BAO_CAO_B4_META) {
            groups.push({
                id: `b4_meta_${meta.key}`,
                label: meta.label,
                span: 1,
                rowspan: 2,
                column: null,
            });
        }
        const months = this.getCalendarMonths();
        for (const grp of BAO_CAO_B4_GROUPS) {
            groups.push({
                id: `b4_grp_${grp.key}`,
                label: grp.label,
                span: months.length || 1,
                rowspan: 1,
                column: null,
            });
        }
        return groups;
    }

    getQtySubColumns() {
        const out = [];
        for (const grp of BAO_CAO_B4_GROUPS) {
            for (const monthKey of this.getCalendarMonths()) {
                out.push({
                    id: `${grp.key}_${monthKey}`,
                    label: `Tháng ${monthKey}`,
                    groupKey: grp.key,
                    monthKey,
                });
            }
        }
        return out;
    }

    getMergeColumns() {
        return [];
    }
}

registerBaoCaoListView("vat_tu_bao_cao_b3_list_view", VatTuBaoCaoB3PivotRenderer);
registerBaoCaoListView("vat_tu_bao_cao_b4_list_view", VatTuBaoCaoB4PivotRenderer);

// ---------------------------------------------------------------------------
// 6) Báo cáo định mức vật tư trung bình — pivot ĐV SX × (Tháng → SL SP / NVL / ĐMBQ)
// ---------------------------------------------------------------------------

function getDmtbColumns(list) {
    const raw = list?.context?.bao_cao_dmtb_columns;
    if (!raw) {
        return [];
    }
    try {
        const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

function parseDmtbMetrics(record) {
    try {
        const parsed = JSON.parse(record?.data?.metrics_json || "[]");
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

function getDmtbSlLabel(list) {
    const raw = (list?.context?.bao_cao_dmtb_sl_label || "").trim();
    return raw || "SL sản phẩm";
}

function getDmtbMetrics(list) {
    const slLabel = getDmtbSlLabel(list);
    return [
        { key: "sp", label: slLabel, metricKey: "sl_sp" },
        { key: "nvl", label: "SL NVL (kg)", metricKey: "sl_nvl" },
        { key: "dmbq", label: "Vật tư bình quân", highlight: true },
    ];
}

class VatTuBaoCaoDmtbPivotRenderer extends VatTuMergedHeaderRenderer {
    static template = "sonha_vat_tu.VatTuBaoCaoDmtbPivotRenderer";

    get displayOptionalFields() {
        return false;
    }

    getColumns() {
        return getDmtbColumns(this.props.list);
    }

    getPivotRows() {
        return [...this.props.list.records].sort((a, b) =>
            String(a.data.company_code || "").localeCompare(String(b.data.company_code || ""))
        );
    }

    metricValue(record, colIndex, metric) {
        const cell = parseDmtbMetrics(record)[colIndex] || {};
        if (metric.key === "dmbq") {
            const sp = cell.sl_sp || 0;
            const nvl = cell.sl_nvl || 0;
            return sp ? nvl / sp : 0;
        }
        return cell[metric.metricKey] || 0;
    }

    formatMetric(value, metric) {
        if (metric.key === "dmbq") {
            if (!value) {
                return "-";
            }
            return formatFloat(value, { digits: [16, 4] });
        }
        if (!value) {
            return "-";
        }
        return formatFloat(value, { digits: [16, 3] });
    }

    getColumnGroups() {
        const groups = [
            {
                id: "dmtb_company",
                label: "Công ty",
                span: 1,
                rowspan: 2,
                column: null,
            },
        ];
        const columns = this.getColumns();
        for (let i = 0; i < columns.length; i++) {
            const colDef = columns[i];
            const label = colDef.label || colDef.month_key || `T${i}`;
            groups.push({
                id: `dmtb_month_${i}`,
                label,
                span: 3,
                rowspan: 1,
                column: null,
            });
        }
        groups.push({
            id: "dmtb_ghi_chu",
            label: "Ghi chú",
            span: 1,
            rowspan: 2,
            column: null,
        });
        return groups;
    }

    getMetricSubColumns() {
        const out = [];
        const columns = this.getColumns();
        const metrics = getDmtbMetrics(this.props.list);
        for (let i = 0; i < columns.length; i++) {
            const colDef = columns[i];
            const monthLabel = colDef.label || colDef.month_key || `T${i}`;
            for (const metric of metrics) {
                out.push({
                    id: `${monthLabel}_${metric.key}_${i}`,
                    label: metric.label,
                    colIndex: i,
                    metric,
                });
            }
        }
        return out;
    }

    getMergeColumns() {
        return [];
    }

    async onGhiChuInput(record, ev) {
        await saveReportLineGhiChu(this.env, record, ev.target.value);
    }
}

registerBaoCaoListView("vat_tu_bao_cao_dmtb_list_view", VatTuBaoCaoDmtbPivotRenderer);

// ---------------------------------------------------------------------------
// 7) Biểu 2 — Chi tiết vật tư cần in (Tổng + công ty động)
// ---------------------------------------------------------------------------

const VTCD_METRICS_FULL = [
    { key: "sl_dat_mua", label: "SL đặt mua", date: "period" },
    { key: "moq", label: "MOQ", date: "period" },
    { key: "sl_dieu_chuyen", label: "SL điều chuyển nội bộ", date: "none" },
    { key: "sl_ton_kho", label: "SL tồn kho", date: "ton_kho" },
    { key: "sl_can_dung", label: "SL cần dùng", date: "period" },
    { key: "vong_quay", label: "Vòng quay hàng tồn kho", date: "none" },
];

const VTCD_METRICS_TRINH_LD = [
    { key: "sl_dat_mua", label: "SL đặt mua", date: "period" },
    { key: "moq", label: "MOQ", date: "period" },
];

const VTCD_FIXED_COLS = [
    { key: "ma_nvl", label: "Mã NVL" },
    { key: "ten_nvl", label: "Tên NVL" },
    { key: "chat_lieu", label: "Chất liệu" },
    { key: "do_bong", label: "Độ bóng" },
    { key: "do_day", label: "Độ dày" },
    { key: "kho_rong", label: "Khổ rộng" },
];

function parseVtcdJson(list, key, fallback) {
    const raw = list?.context?.[key];
    if (!raw) {
        return fallback;
    }
    try {
        return typeof raw === "string" ? JSON.parse(raw) : raw;
    } catch {
        return fallback;
    }
}

function getVtcdCompanies(list) {
    const parsed = parseVtcdJson(list, "bao_cao_vtcd_companies", []);
    return Array.isArray(parsed) ? parsed : [];
}

function getVtcdMetrics(list) {
    const kind = list?.context?.bao_cao_vtcd_report_kind || "kiem_tra";
    return kind === "trinh_ld" ? VTCD_METRICS_TRINH_LD : VTCD_METRICS_FULL;
}

function getVtcdPeriodMonth(list) {
    return (list?.context?.bao_cao_vtcd_period_month || "").trim();
}

function getVtcdTonKhoMonth(list) {
    return (list?.context?.bao_cao_vtcd_ton_kho_month || "").trim();
}

function parseVtcdMetrics(record) {
    try {
        const parsed = JSON.parse(record?.data?.metrics_json || "{}");
        return parsed && typeof parsed === "object" ? parsed : {};
    } catch {
        return {};
    }
}

function vtcdMetricDate(list, metric) {
    if (metric.date === "period") {
        return getVtcdPeriodMonth(list);
    }
    if (metric.date === "ton_kho") {
        return getVtcdTonKhoMonth(list);
    }
    return "";
}

class VatTuBaoCaoVtcdPivotRenderer extends VatTuMergedHeaderRenderer {
    static template = "sonha_vat_tu.VatTuBaoCaoVtcdPivotRenderer";

    get displayOptionalFields() {
        return false;
    }

    getFixedCols() {
        return VTCD_FIXED_COLS;
    }

    getPivotRows() {
        return [...this.props.list.records].sort(
            (a, b) => (a.data.sequence || 0) - (b.data.sequence || 0)
        );
    }

    isSubtotalRow(record) {
        return (record?.data?.row_type || "detail") !== "detail";
    }

    fixedCellValue(record, col) {
        if (this.isSubtotalRow(record)) {
            if (col.key === "kho_rong") {
                return record.data.label || "";
            }
            return "";
        }
        return record.data[col.key] || "";
    }

    metricBlocks() {
        const blocks = [{ id: "total", label: "Tổng", scope: "total" }];
        for (const comp of getVtcdCompanies(this.props.list)) {
            blocks.push({
                id: `co_${comp.code}`,
                label: comp.label || comp.code,
                scope: comp.code,
            });
        }
        return blocks;
    }

    flatMetricColumns() {
        const out = [];
        const metrics = getVtcdMetrics(this.props.list);
        for (const block of this.metricBlocks()) {
            for (const metric of metrics) {
                out.push({
                    id: `${block.id}_${metric.key}`,
                    block,
                    metric,
                });
            }
        }
        return out;
    }

    metricValue(record, block, metric) {
        const payload = parseVtcdMetrics(record);
        const bucket =
            block.scope === "total"
                ? payload.total || {}
                : (payload.companies || {})[block.scope] || {};
        return bucket[metric.key] || 0;
    }

    formatMetric(value) {
        if (value === null || value === undefined || value === "") {
            return "-";
        }
        const num = Number(value);
        if (Number.isNaN(num)) {
            return value;
        }
        if (Math.abs(num - Math.round(num)) < 1e-6) {
            return String(Math.round(num));
        }
        return formatFloat(num, { digits: [16, 2] });
    }

    getColumnGroups() {
        const groups = VTCD_FIXED_COLS.map((col) => ({
            id: `vtcd_fix_${col.key}`,
            label: col.label,
            span: 1,
            rowspan: 3,
            column: null,
        }));
        const metrics = getVtcdMetrics(this.props.list);
        for (const block of this.metricBlocks()) {
            groups.push({
                id: block.id,
                label: block.label,
                span: metrics.length,
                rowspan: 1,
                column: null,
            });
        }
        groups.push({
            id: "vtcd_ghi_chu",
            label: "Ghi chú",
            span: 1,
            rowspan: 3,
            column: null,
        });
        return groups;
    }

    getMetricSubColumns() {
        return this.flatMetricColumns().map((col) => ({
            id: col.id,
            label: col.metric.label,
            col,
        }));
    }

    getMetricDateColumns() {
        const list = this.props.list;
        return this.flatMetricColumns().map((col) => ({
            id: `${col.id}_date`,
            label: vtcdMetricDate(list, col.metric),
            col,
        }));
    }

    getMergeColumns() {
        return [];
    }

    async onGhiChuInput(record, ev) {
        await saveReportLineGhiChu(this.env, record, ev.target.value);
    }
}

class VatTuBaoCaoVtcdListController extends VatTuBaoCaoListController {
    /** Kiểm tra: chỉ Excel; trình lãnh đạo: Excel + PDF. */
    get baoCaoCogMenuItems() {
        const menus = super.baoCaoCogMenuItems;
        const kind = this.props.context?.bao_cao_vtcd_report_kind || "kiem_tra";
        const filterItems = (items) =>
            (items || []).filter((item) => {
                const name = (item.name || "").toLowerCase();
                if (name.includes("pdf")) {
                    return kind === "trinh_ld";
                }
                return true;
            });
        return {
            action: filterItems(menus.action),
            print: filterItems(menus.print),
        };
    }
}

registerBaoCaoListView(
    "vat_tu_bao_cao_vtcd_list_view",
    VatTuBaoCaoVtcdPivotRenderer,
    VatTuBaoCaoVtcdListController,
);

// ---------------------------------------------------------------------------
// 8) Biểu 5 Bảng 2 — Tổng hợp KH đặt sản xuất
// ---------------------------------------------------------------------------

const KH_DSX_GROUPS = [
    { key: "qty_sx", label: "Kế hoạch sản xuất" },
    { key: "qty_kd", label: "Kế hoạch kinh doanh đặt sản xuất" },
    { key: "qty_cl", label: "Chênh lệch KHSX-KH đặt hàng" },
    { key: "ty_le", label: "Tỷ lệ chênh lệch" },
];

function getKhDsxMonths(list) {
    const raw = list?.context?.bao_cao_khdsx_columns;
    if (!raw) {
        return [];
    }
    try {
        const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (!Array.isArray(parsed)) {
            return [];
        }
        return parsed.map((col) => col.label || col.month_key || "").filter(Boolean);
    } catch {
        return [];
    }
}

function getKhDsxTonMonth(list) {
    return (list?.context?.bao_cao_khdsx_ton_month || "").trim();
}

function parseKhDsxMetrics(record) {
    try {
        const parsed = JSON.parse(record?.data?.metrics_json || "[]");
        if (!Array.isArray(parsed)) {
            return {};
        }
        const byMonth = {};
        for (const cell of parsed) {
            if (cell?.month_key) {
                byMonth[cell.month_key] = cell;
            }
        }
        return byMonth;
    } catch {
        return {};
    }
}

class VatTuBaoCaoKhDsxPivotRenderer extends VatTuMergedHeaderRenderer {
    static template = "sonha_vat_tu.VatTuBaoCaoKhDsxPivotRenderer";

    get displayOptionalFields() {
        return false;
    }

    getCalendarMonths() {
        return getKhDsxMonths(this.props.list);
    }

    getTonHeaderLabel() {
        const month = getKhDsxTonMonth(this.props.list);
        if (!month) {
            return "Tồn đầu kỳ";
        }
        return `Tồn kho cuối kỳ T${month}`;
    }

    getPivotRows() {
        return [...this.props.list.records].sort((a, b) => {
            const sx = String(a.data.company_sx_code || "");
            const sxB = String(b.data.company_sx_code || "");
            if (sx !== sxB) {
                return sx.localeCompare(sxB);
            }
            const dat = String(a.data.company_dat_code || "");
            const datB = String(b.data.company_dat_code || "");
            if (dat !== datB) {
                return dat.localeCompare(datB);
            }
            return String(a.data.nganh_hang || "").localeCompare(String(b.data.nganh_hang || ""));
        });
    }

    metricValue(record, monthKey, metricKey) {
        const bucket = parseKhDsxMetrics(record)[monthKey] || {};
        return bucket[metricKey] || 0;
    }

    formatQty(value) {
        return formatFloat(value || 0, { digits: [16, 2] });
    }

    formatMetric(value, metricKey) {
        if (metricKey === "ty_le") {
            return formatFloat((value || 0) * 100, { digits: [16, 2] }) + "%";
        }
        return this.formatQty(value);
    }

    getColumnGroups() {
        const groups = [
            {
                id: "khdsx_company_sx",
                label: "Công ty sản xuất",
                span: 1,
                rowspan: 2,
                column: null,
            },
            {
                id: "khdsx_company_dat",
                label: "Công ty đặt hàng",
                span: 1,
                rowspan: 2,
                column: null,
            },
            {
                id: "khdsx_nganh",
                label: "Ngành hàng",
                span: 1,
                rowspan: 2,
                column: null,
            },
            {
                id: "khdsx_ton",
                label: this.getTonHeaderLabel(),
                span: 1,
                rowspan: 2,
                column: null,
            },
        ];
        const months = this.getCalendarMonths();
        for (const grp of KH_DSX_GROUPS) {
            groups.push({
                id: `khdsx_grp_${grp.key}`,
                label: grp.label,
                span: months.length || 1,
                rowspan: 1,
                column: null,
            });
        }
        groups.push({
            id: "khdsx_ghi_chu",
            label: "Ghi chú",
            span: 1,
            rowspan: 2,
            column: null,
        });
        return groups;
    }

    getQtySubColumns() {
        const out = [];
        for (const grp of KH_DSX_GROUPS) {
            for (const monthKey of this.getCalendarMonths()) {
                out.push({
                    id: `${grp.key}_${monthKey}`,
                    label: `T${monthKey}`,
                    groupKey: grp.key,
                    monthKey,
                });
            }
        }
        return out;
    }

    getMergeColumns() {
        return [];
    }

    async onGhiChuInput(record, ev) {
        await saveReportLineGhiChu(this.env, record, ev.target.value);
    }
}

registerBaoCaoListView("vat_tu_bao_cao_khdsx_list_view", VatTuBaoCaoKhDsxPivotRenderer);
