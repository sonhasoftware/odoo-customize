/** @odoo-module */
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";

import { Component, useState } from "@odoo/owl";

export class RecordsSelectorPopover extends Component {
    static components = { MultiRecordSelector };
    static template = "ai.RecordsSelectorPopover";
    static props = {
        resModel: { type: String },
        close: { type: Function },
        domain: { type: Array, optional: true },
        validate: { type: Function },
        resIds: { type: Array, optional: true },
    };

    setup() {
        this.state = useState({
            resIds: this.props.resIds || [],
        });
    }

    update(resIds) {
        this.state.resIds = resIds;
    }

    validate() {
        this.props.validate(this.state.resIds);
        this.props.close();
    }
}
