/** @odoo-module */
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { session } from "@web/session";

export const aiNaturalLanguageService = {
    dependencies: ["bus_service", "action", "menu", "dialog"],
    start(env, { bus_service, action: actionService, menu: menuService, dialog: dialogService }) {
        bus_service.subscribe(
            "AI_OPEN_MENU_LIST",
            async ({
                menuID,
                selectedFilters,
                selectedGroupBys,
                search,
                customDomain,
                aiSessionIdentifier,
            }) => {
                if (aiSessionIdentifier !== session.ai_session_identifier) {
                    return;
                }
                const menu = await menuService.getMenu(menuID);
                if (!menu.actionID) {
                    return;
                }
                const aiProps = { selectedFilters, selectedGroupBys, search };
                if (customDomain) {
                    aiProps.customDomain = customDomain;
                }
                await actionService.doAction(menu.actionID, {
                    props: { ai: aiProps },
                    viewType: "list",
                });
            }
        );
        bus_service.subscribe(
            "AI_OPEN_MENU_KANBAN",
            async ({
                menuID,
                selectedFilters,
                selectedGroupBys,
                search,
                customDomain,
                aiSessionIdentifier,
            }) => {
                if (aiSessionIdentifier !== session.ai_session_identifier) {
                    return;
                }
                const menu = await menuService.getMenu(menuID);
                if (!menu.actionID) {
                    return;
                }
                const aiProps = { selectedFilters, selectedGroupBys, search };
                if (customDomain) {
                    aiProps.customDomain = customDomain;
                }
                await actionService.doAction(menu.actionID, {
                    props: { ai: aiProps },
                    viewType: "kanban",
                });
            }
        );
        bus_service.subscribe(
            "AI_OPEN_MENU_PIVOT",
            async ({
                menuID,
                selectedFilters,
                rowGroupBys,
                colGroupBys,
                measures,
                search,
                sortedColumn,
                customDomain,
                aiSessionIdentifier,
            }) => {
                if (aiSessionIdentifier !== session.ai_session_identifier) {
                    return;
                }
                const menu = await menuService.getMenu(menuID);
                if (!menu.actionID) {
                    return;
                }
                const aiProps = {
                    selectedFilters,
                    selectedGroupBys: rowGroupBys,
                    colGroupBys,
                    measures,
                    search,
                };
                if (sortedColumn) {
                    aiProps.sortedColumn = sortedColumn;
                }
                if (customDomain) {
                    aiProps.customDomain = customDomain;
                }
                await actionService.doAction(menu.actionID, {
                    props: { ai: aiProps },
                    viewType: "pivot",
                });
            }
        );
        bus_service.subscribe(
            "AI_OPEN_MENU_GRAPH",
            async ({
                menuID,
                selectedFilters,
                groupBys,
                measure,
                mode,
                order,
                stacked,
                cumulated,
                search,
                customDomain,
                aiSessionIdentifier,
            }) => {
                if (aiSessionIdentifier !== session.ai_session_identifier) {
                    return;
                }
                const menu = await menuService.getMenu(menuID);
                if (!menu.actionID) {
                    return;
                }
                const aiProps = {
                    selectedFilters,
                    groupBys,
                    measure,
                    mode,
                    order,
                    stacked,
                    cumulated,
                    search,
                };
                if (customDomain) {
                    aiProps.customDomain = customDomain;
                }
                await actionService.doAction(menu.actionID, {
                    props: { ai: aiProps },
                    viewType: "graph",
                });
            }
        );
        bus_service.subscribe(
            "AI_ADJUST_SEARCH",
            async ({
                removeFacets,
                toggleFilters,
                toggleGroupBys,
                applySearches,
                measures,
                mode,
                order,
                stacked,
                cumulated,
                switchViewType,
                customDomain,
            }) => {
                async function trySwitchView() {
                    try {
                        if (switchViewType) {
                            await actionService.switchView(switchViewType);
                        }
                    } catch (error) {
                        dialogService.add(AlertDialog, {
                            body: _t(
                                "Tried to switch to %s but the app is no longer in an action window.",
                                switchViewType
                            ),
                            title: _t("Unable to switch view"),
                            confirm: () => {},
                            confirmLabel: _t("Close"),
                        });
                        return error;
                    }
                }
                // switch view before applying the changes to the search bar because switching view
                // will rerender the action container with the search bar. Any search bar changes from the
                // previous action container won't be reflected if we don't wait for the new view.
                const error = await trySwitchView();
                if (!error) {
                    env.bus.trigger("APPLY_AI_ADJUST_SEARCH", {
                        removeFacets,
                        toggleFilters,
                        toggleGroupBys,
                        applySearches,
                        measures,
                        mode,
                        order,
                        stacked,
                        cumulated,
                        customDomain,
                    });
                }
            }
        );
        bus_service.start();
    },
};

registry.category("services").add("ai_natural_language_service", aiNaturalLanguageService);
