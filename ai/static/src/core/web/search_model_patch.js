/** @odoo-module */
import { SearchModel } from "@web/search/search_model";
import { patch } from "@web/core/utils/patch";
import { GROUPABLE_TYPES } from "@web/search/utils/misc";

const CHAR_FIELDS = ["char", "html", "many2many", "many2one", "one2many", "text", "properties"];

patch(SearchModel.prototype, {
    validateField(fieldName, field) {
        const { groupable, type } = field;
        return groupable && fieldName !== "id" && GROUPABLE_TYPES.includes(type);
    },
    async applyAISearch({ filters, groupBys, fieldSearches, customDomain }) {
        // TODO JCB: support dateGroupBy and fieldProperty
        // TODO JCB: name vs fieldName, which one to use?
        for (const filter of filters || []) {
            const [searchItem] = this.getSearchItems(
                (i) => i.type === "filter" && [i.name, i.fieldName].includes(filter)
            );
            if (searchItem && !searchItem?.isActive) {
                this.toggleSearchItem(searchItem.id);
            }
        }
        for (const groupBy of groupBys || []) {
            const [searchItem] = this.getSearchItems(
                (i) => i.type === "groupBy" && [i.name, i.fieldName].includes(groupBy)
            );

            if (searchItem && !searchItem?.isActive) {
                this.toggleSearchItem(searchItem.id);
            } else if (!searchItem) {
                const field = this.searchViewFields[groupBy];
                if (!field || !this.validateField(groupBy, field)) {
                    continue;
                }
                this.createNewGroupBy(groupBy);
            }
        }
        for (const searchString of fieldSearches || []) {
            const separatorIndex = searchString.indexOf("=");
            if (separatorIndex === -1) {
                console.warn(
                    `Invalid search format: "${searchString}". Expected format: "field=text"`
                );
                continue;
            }
            const fieldName = searchString.substring(0, separatorIndex);
            const value = searchString.substring(separatorIndex + 1);

            const [searchItem] = this.getSearchItems(
                (i) => i.type === "field" && i.fieldName === fieldName
            );
            if (searchItem) {
                this.addAutoCompletionValues(searchItem.id, {
                    value,
                    label: value,
                    operator:
                        searchItem.operator ||
                        (CHAR_FIELDS.includes(searchItem.fieldType) ? "ilike" : "="),
                });
            }
        }
        if (customDomain && customDomain.length) {
            await this.splitAndAddDomain(customDomain);
        }
    },
    async load(config) {
        const result = await super.load(config);
        if (config.ai) {
            await this.applyAISearch({
                filters: config.ai.selectedFilters,
                groupBys: config.ai.selectedGroupBys,
                fieldSearches: config.ai.search,
                customDomain: config.ai.customDomain,
            });
        }
        return result;
    },
});
