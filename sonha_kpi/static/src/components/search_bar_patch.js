/** @odoo-module **/

import { SearchBar } from "@web/search/search_bar/search_bar";
import { patch } from "@web/core/utils/patch";

patch(SearchBar.prototype, {
    getItems(searchItem, trimmedQuery) {
        const resModel = this.env.searchModel?.resModel;
        const targetModels = ["parent.kpi.year", "parent.kpi.month", "company.sonha.kpi"];

        if (targetModels.includes(resModel)) {
            const isNumeric = /^\d+$/.test(trimmedQuery);
            const fieldName = searchItem.fieldName;

            if (isNumeric) {
                // If the user types a number, do not show autocomplete suggestion for 'department_id' (Phòng ban)
                if (fieldName === "department_id") {
                    return [];
                }
            } else {
                // If the user types text, do not show autocomplete suggestion for 'month' (Tháng) or 'year' (Năm)
                if (fieldName === "month" || fieldName === "year") {
                    return [];
                }
            }
        }
        return super.getItems(searchItem, trimmedQuery);
    }
});
