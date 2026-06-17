/** @odoo-module */
import { registry } from "@web/core/registry";
import { formatDate, formatDateTime } from "@web/core/l10n/dates";
import { browser } from "@web/core/browser/browser";


export const aiChatLauncherService = {
    dependencies: ["mail.store", "orm"],
    start(env, services) {
        return {
            async launchAIChat({
                callerComponentName,
                recordModel,
                recordId,
                channelTitle,
                aiSpecialActions,
                aiChatSourceId,
                originalRecordData = null,
                originalRecordFields = null,
                textSelection = null,
            }) {
                let frontEndRecordInfo;
                // if the component calling the AI has access to record info, we pass it straight to the AI
                if (['html_field_record', 'html_field_text_select', 'chatter_ai_button'].includes(callerComponentName)) {
                    frontEndRecordInfo = this.recordDataToContextJSON(originalRecordData, originalRecordFields);
                }
                // make the insert button target the component that called the AI
                services['mail.store'].aiInsertButtonTarget = aiChatSourceId;
                
                const { ai_channel_id, data, prompts } = await services.orm.call(
                    'discuss.channel',
                    'create_ai_draft_channel',
                    [
                        callerComponentName,
                        channelTitle,
                        recordModel,
                        recordId,
                        frontEndRecordInfo,
                        textSelection,
                    ],
                );

                let thread;
                if (data.Thread) {
                    thread = services['mail.store'].Thread.insert(data.Thread);
                } else {
                    thread = services['mail.store'].Thread.insert({
                        model: "discuss.channel",
                        id: Number(ai_channel_id),
                    });
                }
                
                if (!thread.is_pinned) {
                    await env.services["mail.thread"].fetchChannel(thread.id);
                }
                browser.localStorage.setItem("ai.thread.prompt_buttons.".concat(thread.id), JSON.stringify(prompts));
                thread.ai_prompt_buttons = prompts;
                thread.aiSpecialActions = aiSpecialActions;
                thread.aiChatSource = aiChatSourceId;
                env.services["mail.thread"].open(thread);
            },
            /**
             * Converts record data to JSON, so we can pass them to the AI record's context
             * @returns {String} String JSON representation of the record
             */
            recordDataToContextJSON(recordData, fieldsInfo) {
                const result = {};

                for (const fieldName in recordData) {
                    if (!recordData.hasOwnProperty(fieldName)) continue;
                    const fieldValue = recordData[fieldName];
                    const fieldInfo = fieldsInfo[fieldName] || {};
                    // Skip binary fields entirely - there is no easy way of placing them in the context
                    if (fieldInfo.type === 'binary') {
                        continue;
                    }
                    // Handle relational fields
                    if (['many2one', 'many2many', 'one2many'].includes(fieldInfo.type)) {
                        // Skip abnormally large relational fields which can floud the AI context
                        if (fieldValue && fieldValue.records && fieldValue.records.length > 50) {
                            continue;
                        }
                        switch (fieldInfo.type) {
                            case 'many2one':
                                result[fieldName] = fieldValue ? fieldValue.display_name || fieldValue.name : null;
                                break;
                            case 'many2many':
                            case 'one2many':
                                if (fieldValue && fieldValue.records) {
                                    result[fieldName] = fieldValue.records.map(record => 
                                        record.data.display_name || record.data.name
                                    );
                                } else {
                                    result[fieldName] = [];
                                }
                                break;
                        }
                    } else if (fieldInfo.type === 'date' && fieldValue) {  // handle date fields
                        const date = luxon.DateTime.fromISO(fieldValue);
                        result[fieldName] = date.isValid ? formatDate(date) : fieldValue;
                    } else if (fieldInfo.type === 'datetime' && fieldValue) {  // handle datetime fields
                        const datetime = luxon.DateTime.fromISO(fieldValue);
                        result[fieldName] = datetime.isValid ? formatDateTime(datetime) : fieldValue;
                    } else {  // handle all other types of fields
                        result[fieldName] = fieldValue;
                    }
                }
                return result;
            },
        };
    },
};

registry.category("services").add("aiChatLauncher", aiChatLauncherService);
