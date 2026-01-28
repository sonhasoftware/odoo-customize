/** @odoo-module */

import { registry } from "@web/core/registry";

const { Component, xml } = owl;

class WelcomeImage extends Component {}

WelcomeImage.template = xml`
    <div style="text-align: center;">
        <img src="/sonha_dau_trang/static/img/ttc.jpg"
             style="max-width: 80%; border-radius: 12px;"/>
    </div>
`;

registry.category("actions").add("welcome_image_client", WelcomeImage);
