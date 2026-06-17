/** @odoo-module */
import { useComponent } from "@odoo/owl";
import { useBus } from "@web/core/utils/hooks";

export async function getCurrentViewInfo(bus) {
    return new Promise((resolve) => {
        const listener = ({ detail }) => {
            bus.removeEventListener("SEND_VIEW_DETAILS!", listener);
            clearTimeout(timeout);
            resolve(detail);
        };
        const timeout = setTimeout(() => {
            bus.removeEventListener("SEND_VIEW_DETAILS!", listener);
            resolve(null);
        }, 100); // Timeout to avoid waiting indefinitely
        bus.addEventListener("SEND_VIEW_DETAILS!", listener);
        bus.trigger("REQUEST_VIEW_DETAILS?");
    });
}

/**
 * The component that can provide the view details should call this hook provided with the callback that can give the view details.
 * Once called, the `getCurrentViewInfo` can then return the current view information which is provided by the callback and is transmitted via the bus.
 */
export function useViewDetailsGetter(getter) {
    const component = useComponent();
    const bus = component.env.bus;
    if (!bus) {
        throw new Error("Bus is not available in the current environment.");
    }
    useBus(bus, "REQUEST_VIEW_DETAILS?", async () => {
        bus.trigger("SEND_VIEW_DETAILS!", await getter());
    });
}
