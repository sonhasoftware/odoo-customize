/** @odoo-module **/

import { registry } from "@web/core/registry";
import { formatFloat } from "@web/views/fields/formatters";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { useEffect } from "@odoo/owl";
import { ListRenderer } from "@web/views/list/list_renderer";
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

function getPeriodMonth(list) {
    const parent = list && list._parent;
    if (parent && parent.resModel === "ke.hoach.vat.tu" && parent.data) {
        return parent.data.period_month || "";
    }
    try {
        const root = list && list.model && list.model.root;
        if (root && root.resModel === "ke.hoach.vat.tu" && root.data) {
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
        ve_du_kien_t: "Hàng đi đường",
        vt_can_dung_t: "Cần dùng",
        ton_cuoi_t: "Tồn cuối",
        so_luong_du_phong_t: "Dự phòng",
        so_luong_thieu_t: "Thiếu",
        so_luong_can_mua_t: "Cần mua",
        tong_ton_nvl_sl_t: "Tồn NVL",
        tong_hang_di_duong_sl_t: "Hàng đi đường",
        tong_sl_vt_can_dung_t: "Vật tư cần dùng",
        sl_du_tru_toi_thieu_t: "Dự trữ tối thiểu",
        sl_can_mua_theo_moq_t: "Cần mua theo MOQ",
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
    ve_du_kien_t: "Hàng đi đường",
    vt_can_dung_t: "Cần dùng",
    ton_cuoi_t: "Tồn cuối",
};

const B5_PREFIX = {
    tong_sl_vt_can_dung_t: "Cần dùng",
    tong_hang_di_duong_sl_t: "Đi đường",
};

const NHU_CAU_PREFIX = {
    so_luong_t: "Sản lượng vật tư cần dùng (Kg)",
};

function getMonthlyMergeInfo(fieldName, prefixMap) {
    if (!fieldName) {
        return null;
    }
    for (const [prefix, categoryLabel] of Object.entries(prefixMap)) {
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
    static template = "sonha_vat_tu.VatTuMergedB4HeaderRenderer";

    getColumnGroups() {
        return this._buildColumnGroups((n) => getMonthlyMergeInfo(n, B4_PREFIX), "b4");
    }

    getMergeColumns() {
        return this._buildMergeColumns((n) => getMonthlyMergeInfo(n, B4_PREFIX), labelThang);
    }
}

class VatTuMergedB5HeaderRenderer extends VatTuMergedHeaderRenderer {
    static template = "sonha_vat_tu.VatTuMergedB5HeaderRenderer";

    getColumnGroups() {
        return this._buildColumnGroups((n) => getMonthlyMergeInfo(n, B5_PREFIX), "b5");
    }

    getMergeColumns() {
        return this._buildMergeColumns((n) => getMonthlyMergeInfo(n, B5_PREFIX), labelThang);
    }
}

function registerMergedView(key, Renderer) {
    registry.category("views").add(key, { ...listView, Renderer });
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
    static template = "sonha_vat_tu.VatTuMergedB4HeaderRenderer";

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
