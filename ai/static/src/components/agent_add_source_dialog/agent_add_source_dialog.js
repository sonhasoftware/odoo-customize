/** @odoo-module **/

import { Component, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { Dialog } from "@web/core/dialog/dialog";
import { getDataURLFromFile } from "@web/core/utils/urls";

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";


class AgentSourceCard extends Component {
    static template = "ai.AgentSourceCard";
    static props = {
        icon: String,
        image: { type: String, optional: true },
        title: String,
        onClick:  { type: Function },
    };
}


class AgentSourceURLDialog extends Component {
    static template = "ai.AgentSourceURLDialog";
    static components = {
        Dialog,
    };

    static props = {
        addURLSources:  { type: Function },
        close:  { type: Function },
    };

    setup() {
        super.setup();
        this.state = useState({
            urls: "",
        });
    }

    onConfirm() {
        this.props.addURLSources(this.state.urls);
        this.props.close();
    }
}


export class AgentSourceAddDialog extends Component {
    static template = "ai.AgentSourceAddDialog";
    static props = {
        agentId: Number,
        close:  { type: Function },
    };
    static components = { AgentSourceCard, Dialog };

    setup() {
        this.agentId = this.props.agentId;
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.fileInputRef = useRef("fileInput");
        this.actionService = useService("action");
        this.dialog = useService("dialog");
        this.state = useState({
            loading: false,
        })
    }

    onAddFileSourceClick() {
        this.fileInputRef.el.click();
    }

    validateFileTypes(files) {
        const allowedExtensions = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.odt', '.ods', '.txt'];
        const validFiles = [];
        const invalidFiles = [];
        for (const file of files) {
            const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
            if (allowedExtensions.includes(fileExtension)) {
                validFiles.push(file);
            } else {
                invalidFiles.push(file);
            }
        }

        return { validFiles, invalidFiles };
    }

    async addAttachmentSources(ev) {
        const files = ev.target.files;
        if (!files || !files.length) {
            return;
        }

        // Validate file types
        const { validFiles, invalidFiles } = this.validateFileTypes(Array.from(files));
        if (invalidFiles.length > 0 && validFiles.length > 0) {
            const invalidFileNames = invalidFiles.map(file => file.name).join(', ');
            this.notification.add(
                _t("Some files have invalid formats and were skipped: %s. Only PDF, Word, PowerPoint, Excel, Text, and OpenDocument files are allowed.", invalidFileNames),
                {
                    type: "warning",
                }
            );
        }

        if (validFiles.length === 0) {
            this.notification.add(
                _t("No valid files to upload. Only PDF, Word, PowerPoint, Excel, Text, and OpenDocument files are allowed."),
                {
                    type: "danger",
                }
            );

            ev.target.value = '';
            return;
        }

        this.state.loading = true;
        const files_list = await Promise.all(
            validFiles.map(async (file) => ({
                name: file.name,
                datas: (await getDataURLFromFile(file)).split(",")[1],
            }))
        );
        const files_datas = []
        for (const attachment_data of files_list) {
            files_datas.push({
                name: attachment_data.name,
                datas: attachment_data.datas,
            });
        }
        await this.orm.call("ai.agent.source", "create_from_binary_files", [files_datas, this.agentId]);
        this.state.loading = false;
        ev.target.value = '';
        return this.actionService.doAction({type: "ir.actions.client", tag: "soft_reload"});
    }

    onAddLinkSourceClick() {
        this.dialog.add(AgentSourceURLDialog, {
            addURLSources: async (urls_string) => await this.addURLSources(urls_string),
        });
    }

    validateAndFilterURLs(urls_list) {
        const validUrls = [];
        const invalidUrls = [];
        for (const url of urls_list) {
            if (url && (url.startsWith('https://') || url.startsWith('http://') || url.startsWith('ftp://'))) {
                validUrls.push(url);
            } else {
                invalidUrls.push(url);
            }
        }
        return { validUrls, invalidUrls };
    }

    async addURLSources(urls_string) {
        if (!urls_string) {
            return;
        }
        const urls_list = [...new Set(
            urls_string
            .split("\n")
            .map(url => url.trim())
            .filter(url => url !== "")
        )];

        if (urls_list.length > 0) {
            const { validUrls, invalidUrls } = this.validateAndFilterURLs(urls_list);
            if (validUrls.length > 0) {
                this.state.loading = true;
                await this.orm.call("ai.agent.source", "create_from_urls", [validUrls, this.agentId]);
                if (invalidUrls.length > 0) {
                    this.notification.add(
                        _t("Some URLs are invalid and were skipped. URLs must start with http://, https://, or ftp://"),
                        {
                            type: "warning",
                        }
                    );
                }
            } else {
                this.notification.add(
                    _t("No valid URLs found to process."),
                    {
                        type: "danger",
                    }
                );
            }

            this.state.loading = false;
            return this.actionService.doAction({type: "ir.actions.client", tag: "soft_reload"});
        }
    }

    get cardsData() {
        return [
            {
                icon: "fa-file-pdf-o text-danger",
                title: _t("Upload a File"),
                onClick: () => this.onAddFileSourceClick(),
            },
            {
                icon: "fa-link",
                title: _t("Add a Link"),
                onClick: () => this.onAddLinkSourceClick(),
            },
        ];
    }
}

registry.category("actions").add("ai_open_sources_dialog", (env, action) => {
    const params = action.params || {};
    env.services.dialog.add(AgentSourceAddDialog,{
        agentId: params.agent_id,
    });
});
