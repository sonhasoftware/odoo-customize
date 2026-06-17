import { HtmlField } from "@html_editor/fields/html_field";
import { beforeEach, expect, test } from "@odoo/hoot";
import { queryAllTexts, queryOne } from "@odoo/hoot-dom";
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";
import { setSelection } from "@html_editor/../tests/_helpers/selection";
import { insertText } from "@html_editor/../tests/_helpers/user_actions";
import { _makeUser, user } from "@web/core/user";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

class Partner extends models.Model {
    txt = fields.Html({ trim: true });
    _records = [{ id: 1, txt: "<p></p>" }];
}

defineModels([Partner]);
defineMailModels();

let htmlEditor;
beforeEach(() => {
    patchWithCleanup(HtmlField.prototype, {
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

test.tags("desktop");
test("ChatGPT command should only be available for internal users", async () => {
    patchWithCleanup(user, _makeUser({ is_internal_user: false }));
    await mountView({
        type: "form",
        resId: 1,
        resModel: "partner",
        arch: `
            <form>
                <field name="txt" widget="html" />
            </form>`,
    });

    setSelection({ anchorNode: queryOne("[name='txt'] .odoo-editor-editable p"), anchorOffset: 0 });
    await contains(".o_we_power_buttons").hover();
    expect(queryAllTexts(".o_we_power_buttons .power_button:not(.d-none)")).not.toInclude("AI");

    await insertText(htmlEditor, "/");
    await contains(".o-we-command-name").hover();
    expect(queryAllTexts(".o-we-command-name")).not.toInclude("ChatGPT");
});
