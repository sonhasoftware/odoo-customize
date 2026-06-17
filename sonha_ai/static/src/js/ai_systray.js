/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { AiChatWindow } from "./ai_chat_window";

export class AiSystrayItem extends Component {
    setup() {
        this.state = useState({
            isOpen: false
        });
        
        // Listen to global event to open from Command Palette
        window.addEventListener("open-ask-ai", () => {
            this.state.isOpen = true;
        });
    }

    _onClick() {
        this.state.isOpen = !this.state.isOpen;
    }
    
    _onClose() {
        this.state.isOpen = false;
    }
}
AiSystrayItem.template = "sonha_ai.SystrayItem";
AiSystrayItem.components = { AiChatWindow };

// Register in systray
const systrayRegistry = registry.category("systray");
systrayRegistry.add("sonha_ai.systray_item", {
    Component: AiSystrayItem,
}, { sequence: 1 });
