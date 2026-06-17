import { setSelection } from "@html_editor/../tests/_helpers/selection";
import { insertText } from "@html_editor/../tests/_helpers/user_actions";
import { HtmlMailField } from "@mail/views/web/fields/html_mail_field/html_mail_field";
import { beforeEach, expect, test } from "@odoo/hoot";
import { press, queryOne } from "@odoo/hoot-dom";
import { animationFrame, enableTransitions } from "@odoo/hoot-mock";
import {
    defineModels,
    fields,
    models,
    mountView,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { mailModels } from "@mail/../tests/mail_test_helpers";

function setSelectionInHtmlField(selector = "p", fieldName = "body") {
    const anchorNode = queryOne(`[name='${fieldName}'] .odoo-editor-editable ${selector}`);
    setSelection({ anchorNode, anchorOffset: 0 });
    return anchorNode;
}

class CustomMessage extends models.Model {
    _name = "custom.message";
    body = fields.Html();
    _records = [{ id: 1, body: "<p>first</p>" }];
}

defineModels({ ...mailModels, CustomMessage });

let htmlEditor;
beforeEach(() => {
    patchWithCleanup(HtmlMailField.prototype, {
        onEditorLoad(editor) {
            htmlEditor = editor;
            return super.onEditorLoad(...arguments);
        },
        getConfig() {
            const config = super.getConfig();
            config.Plugins = config.Plugins.filter((Plugin) => Plugin.id !== "editorVersion");
            return config;
        },
    });
});

test("HtmlMail should have the AI prompt command when dynamic placeholder plugin is active", async function () {
    enableTransitions();
    await mountView({
        type: "form",
        resId: 1,
        resModel: "custom.message",
        arch: `
        <form>
            <field name="body" widget="html_mail" options="{'dynamic_placeholder': true}"/>
        </form>`,
    });
    setSelectionInHtmlField();
    await insertText(htmlEditor, "/prompt");
    await press("enter");
    expect(".o_editor_prompt").toHaveCount(1);
});

test("Only dynamic placeholder command should be available inside an AI prompt", async function () {
    await mountView({
        type: "form",
        resId: 1,
        resModel: "custom.message",
        arch: `
        <form>
            <field name="body" widget="html_mail" options="{'dynamic_placeholder': true}"/>
        </form>`,
    });
    setSelectionInHtmlField();
    await insertText(htmlEditor, "/prompt");
    await press("enter");
    await insertText(htmlEditor, "/");
    await animationFrame();
    expect(".o-we-command").toHaveCount(1);
    expect(".o-we-command .o-we-command-name").toHaveText("Dynamic Placeholder");
});
