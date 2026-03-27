/** @odoo-module */
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { serializeDate, deserializeDate } from "@web/core/l10n/dates";

export class DateRange extends Component {
    static template = "DateRange";
    static components = { DateTimeInput };
    static props = {
        onFromToChanged: Function,
    };
    fromPlaceholder = _t("Date From");
    toPlaceholder = _t("Date To");

    setup(){
        this.state = owl.useState({
            from: false,
            to: false,
        })
    }
    onDateFromChanged(dateFrom) {
        this.props.onFromToChanged({
            from: dateFrom && serializeDate(dateFrom.startOf("day")),
            to: this.state.to,
        });
        this.state.from = dateFrom && serializeDate(dateFrom.startOf("day"))
    }
    onDateToChanged(dateTo) {
        this.props.onFromToChanged({
            from: this.state.from,
            to: dateTo && serializeDate(dateTo.endOf("day")),
        });
        this.state.to = dateTo && serializeDate(dateTo.endOf("day"))
    }
    get dateFrom() {
        return this.state.from && deserializeDate(this.state.from);
    }
    get dateTo() {
        return this.state.to && deserializeDate(this.state.to);
    }
}
