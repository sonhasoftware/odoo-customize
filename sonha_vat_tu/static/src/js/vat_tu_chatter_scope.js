/* @odoo-module */

import { Chatter } from "@mail/core/web/chatter";
import { ThreadService } from "@mail/core/common/thread_service";
import { onWillUpdateProps } from "@odoo/owl";
import { FormCompiler } from "@web/views/form/form_compiler";
import { patch } from "@web/core/utils/patch";
import { setAttributes } from "@web/core/utils/xml";

const VAT_TU_MODEL = "ke.hoach.vat.tu";
const SCOPES = new Set(["kd", "sx", "vt"]);

function isVatTuScopedThread(thread) {
    return thread?.model === VAT_TU_MODEL && SCOPES.has(thread.vatTuScope);
}

function resetThreadForScope(thread, scope) {
    thread.vatTuScope = scope;
    thread.messages = [];
    thread.pendingNewMessages = [];
    thread.needactionMessages = [];
    thread.isLoaded = false;
    thread.loadOlder = false;
    thread.loadNewer = false;
    thread.status = "new";
}

if (!Chatter.props.includes("vatTuScope?")) {
    Chatter.props.push("vatTuScope?");
}

patch(FormCompiler.prototype, {
    compile(key, params) {
        const sourceTemplate = this.templates?.[key];
        const chatterNode = sourceTemplate?.querySelector?.("div.oe_chatter[data-vat-tu-scope]");
        const scope = chatterNode?.getAttribute("data-vat-tu-scope");
        const res = super.compile(...arguments);
        if (!SCOPES.has(scope)) {
            return res;
        }
        for (const chatterXml of res.querySelectorAll(
            "t[t-component='__comp__.mailComponents.Chatter']"
        )) {
            setAttributes(chatterXml, {
                vatTuScope: `'${scope}'`,
            });
        }
        return res;
    },
});

patch(Chatter.prototype, {
    setup() {
        super.setup(...arguments);
        onWillUpdateProps((nextProps) => {
            this._applyVatTuScope(nextProps.vatTuScope);
        });
    },

    _applyVatTuScope(scope = this.props.vatTuScope) {
        const thread = this.state.thread;
        if (thread?.model !== VAT_TU_MODEL || !SCOPES.has(scope)) {
            return;
        }
        if (thread.vatTuScope !== scope) {
            resetThreadForScope(thread, scope);
        }
    },

    changeThread(threadModel, threadId, webRecord) {
        super.changeThread(...arguments);
        this._applyVatTuScope();
    },

    load(thread, requestList) {
        this._applyVatTuScope();
        return super.load(...arguments);
    },
});

patch(ThreadService.prototype, {
    getFetchRoute(thread) {
        if (isVatTuScopedThread(thread)) {
            return "/sonha_vat_tu/mail/thread/messages";
        }
        return super.getFetchRoute(...arguments);
    },

    getFetchParams(thread) {
        const params = super.getFetchParams(...arguments);
        if (isVatTuScopedThread(thread)) {
            params.vat_tu_scope = thread.vatTuScope;
        }
        return params;
    },

    async getMessagePostParams(params) {
        const result = await super.getMessagePostParams(...arguments);
        const thread = params.thread;
        if (isVatTuScopedThread(thread)) {
            result.context = {
                ...result.context,
                vat_tu_chatter_scope: thread.vatTuScope,
            };
        }
        return result;
    },
});
