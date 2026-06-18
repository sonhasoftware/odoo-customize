/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";

/**
 * Tính label tháng dạng "Tháng MM/YYYY" từ period_month (MM/YYYY) + offset (0..3).
 */
function getMonthLabel(periodMonth, index) {
    if (!periodMonth) return "";
    const parts = periodMonth.split('/');
    if (parts.length !== 2) return "";
    let month = parseInt(parts[0], 10);
    let year = parseInt(parts[1], 10);
    if (isNaN(month) || isNaN(year)) return "";
    month += index;
    while (month > 12) {
        month -= 12;
        year += 1;
    }
    return `Tháng ${String(month).padStart(2, '0')}/${year}`;
}

// Mapping field name → offset tháng
const FIELD_OFFSETS = {
    "qty_t0": 0, "qty_kd_t0": 0, "qty_sx_t0": 0, "qty_cl_t0": 0,
    "qty_t1": 1, "qty_kd_t1": 1, "qty_sx_t1": 1, "qty_cl_t1": 1,
    "qty_t2": 2, "qty_kd_t2": 2, "qty_sx_t2": 2, "qty_cl_t2": 2,
    "qty_t3": 3, "qty_kd_t3": 3, "qty_sx_t3": 3, "qty_cl_t3": 3,
};

/**
 * Lấy period_month từ parent record (dùng cho inline x2many list).
 * list._parent là record cha ke.hoach.vat.tu (StaticList pattern trong Odoo 17).
 */
function _getPeriodMonth(list) {
    const parent = list && list._parent;
    if (parent && parent.resModel === "ke.hoach.vat.tu" && parent.data) {
        return parent.data.period_month || "";
    }
    return "";
}

patch(ListRenderer.prototype, {
    /**
     * Override processAllColumn để gắn label tháng động cho các cột qty_tX.
     * Clone column object trước khi sửa label để tránh mutate archInfo gốc.
     */
    processAllColumn(allColumns, list) {
        const result = super.processAllColumn(allColumns, list);
        const periodMonth = _getPeriodMonth(list);
        if (!periodMonth) {
            return result;
        }
        return result.map((col) => {
            if (col.type === "field" && col.name in FIELD_OFFSETS) {
                const offset = FIELD_OFFSETS[col.name];
                const label = getMonthLabel(periodMonth, offset);
                if (label) {
                    return { ...col, label };
                }
            }
            return col;
        });
    },
});
