import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { AiPrompt } from "@ai/ai_prompt/ai_prompt";
import { setSelection } from "@html_editor/../tests/_helpers/selection";
import { insertText } from "@html_editor/../tests/_helpers/user_actions";
import {
    defineModels,
    fields,
    models,
    mountWithCleanup,
    onRpc,
    patchWithCleanup,
} from "@web/../tests/web_test_helpers";

import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { click, queryOne, press } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { MainComponentsContainer } from "@web/core/main_components_container";

class Dummy extends models.Model {
    _name = "dummy";

    name = fields.Char();
    message_ids = fields.One2many({ relation: "mail.message", string: "Messages" });

    async mail_allowed_qweb_expressions() {
        return ["object.display_name"];
    }

    async ai_find_default_records(comodel, domain, field_name, property_name) {
        return [];
    }

    _records = [
        { id: 1, name: "Bob" },
        { id: 2, name: "Patrick" },
        { id: 3, name: "Sheldon" },
    ];
}

defineMailModels();
defineModels([Dummy]);

describe.current.tags("desktop");

let htmlEditor;
beforeEach(() => {
    patchWithCleanup(AiPrompt.prototype, {
        onEditorLoad(editor) {
            htmlEditor = editor;
            return super.onEditorLoad(...arguments);
        },
    });
});
let updatePromptVal = "";

test("AI Prompt - Readonly", async () => {
    await mountWithCleanup(AiPrompt, {
        props: {
            readonly: true,
            prompt: '<p>Hello <span data-ai-field="name">World</span></p>',
            updatePrompt: () => {},
        },
    });
    expect("span.o_readonly_ai_prompt").toHaveCount(1);
    expect("span.o_readonly_ai_prompt").toHaveText("Hello World");
});

test("AI Prompt - Editable", async () => {
    await mountWithCleanup(AiPrompt, {
        props: {
            model: "dummy",
            updatePrompt: (change) => (updatePromptVal = change),
            prompt: '<p>Hello <span data-ai-field="name">World</span></p>',
        },
    });
    expect("div.o_ai_prompt").toHaveCount(1);
    expect("div.o_ai_prompt").toHaveText("Hello World");
    setSelection({ anchorNode: queryOne(".o_ai_prompt .odoo-editor-editable p"), anchorOffset: 4 });
    await insertText(htmlEditor, " bloups");
    await click(document.body);
    expect(updatePromptVal).toBe(
        '<p>Hello <span data-ai-field="name" data-oe-protected="true">World</span> bloups</p>',
    );
});

test("AI Prompt - Field selector without template editor group", async () => {
    onRpc("has_group", () => false);
    await mountWithCleanup(AiPrompt, {
        props: {
            model: "dummy",
            updatePrompt: (change) => (updatePromptVal = change),
            prompt: "<p>Hello</p>",
        },
    });
    setSelection({ anchorNode: queryOne(".o_ai_prompt .odoo-editor-editable p"), anchorOffset: 1 });
    await insertText(htmlEditor, " /fie");
    await animationFrame();
    expect(".o-we-command").toHaveCount(1);
    expect(".o-we-command .o-we-command-name").toHaveText("Field Selector");
    await click(".o-we-command");
    await animationFrame();
    // only displayname available (see mail_allowed_qweb_expressions)
    expect(".o_model_field_selector_popover_item").toHaveCount(1);
    expect(".o_model_field_selector_popover_item_name").toHaveText("Display name");
    await click(".o_model_field_selector_popover_item_name");
    await animationFrame();
    await click(document.body);
    expect(updatePromptVal).toBe(
        '<p>Hello <span data-ai-field="display_name" data-oe-protected="true">Display name</span>&nbsp;</p>',
    );
    // clicking on the field should reopen the field selector
    await click("div.o_ai_prompt span[data-ai-field]");
    await animationFrame();
    expect(".o_model_field_selector_popover").toHaveCount(1);
});

test("AI Prompt - Field selector with template editor group", async () => {
    await mountWithCleanup(AiPrompt, {
        props: {
            model: "dummy",
            updatePrompt: (change) => (updatePromptVal = change),
            prompt: "<p>Hello</p>",
        },
    });
    setSelection({ anchorNode: queryOne(".o_ai_prompt .odoo-editor-editable p"), anchorOffset: 1 });
    await insertText(htmlEditor, " /fiel");
    await animationFrame();
    await click(".o-we-command");
    await animationFrame();
    await click(".o_model_field_selector_popover_item_name:contains('Created on')");
    await animationFrame();
    await expect(".o_model_field_selector_popover .badge").toHaveCount(1);
    await expect(".o_model_field_selector_popover .badge").toHaveText("Created on");
    await expect(".o_model_field_selector_popover_item_name:contains('Created on')").toHaveCount(0);
    await click(".o_model_field_selector_popover_item_name:contains('Display name')");
    await animationFrame();
    await expect(".o_model_field_selector_popover .badge").toHaveCount(2);
    await click(".btn-primary");
    await animationFrame();
    await click(document.body);
    expect(updatePromptVal).toBe(
        `<p>Hello <span data-ai-field="create_date" data-oe-protected="true">Created on</span>, <span data-ai-field="display_name" data-oe-protected="true">Display name</span>&nbsp;</p>`
    );
    // clicking on the record should reopen the field selector
    await click("div.o_ai_prompt span[data-ai-field]");
    await animationFrame();
    expect(".o_model_field_selector_popover").toHaveCount(1);
});

test("AI prompt - Insert messages", async () => {
    await mountWithCleanup(AiPrompt, {
        props: {
            model: "dummy",
            updatePrompt: (change) => (updatePromptVal = change),
            prompt: "<p>Messages</p>",
        },
    });
    setSelection({ anchorNode: queryOne(".o_ai_prompt .odoo-editor-editable p"), anchorOffset: 1 });
    await insertText(htmlEditor, " /fiel");
    await animationFrame();
    await click(".o-we-command");
    await animationFrame();
    await click(".o_model_field_selector_popover_item_name:contains('Messages')");
    await animationFrame();
    await click(".btn-primary");
    await animationFrame();
    await click(document.body);
    expect(updatePromptVal).toBe(
        '<p>Messages <span data-ai-field="message_ids" data-oe-protected="true">Messages</span>&nbsp;</p>',
    );
});

test("AI Prompt - Without comodel", async () => {
    await mountWithCleanup(AiPrompt, {
        props: {
            model: "dummy",
            updatePrompt: (change) => (updatePromptVal = change),
            prompt: '<p>Hello <span data-ai-field="name">World</span></p>',
        },
    });
    setSelection({ anchorNode: queryOne(".o_ai_prompt .odoo-editor-editable p"), anchorOffset: 1 });
    await insertText(htmlEditor, "/rec");
    await animationFrame();
    // record selector should not be shown
    expect(".o-we-command").toHaveCount(0);
});

test("AI Prompt - With comodel", async () => {
    await mountWithCleanup(AiPrompt, {
        props: {
            comodel: "dummy",
            domain: "[['id', 'in', [1, 2]]]",
            model: "dummy",
            updatePrompt: (change) => (updatePromptVal = change),
            prompt: "<p>Hello</p>",
            missingRecordsWarning: "Missing Records",
        },
    });
    expect(".o_ai_prompt + .alert").toHaveText("Missing Records");
    setSelection({ anchorNode: queryOne(".o_ai_prompt .odoo-editor-editable p"), anchorOffset: 1 });
    insertText(htmlEditor, " /rec");
    await animationFrame();
    expect(".o-we-command").toHaveCount(1);
    expect(".o-we-command-name").toHaveText("Records Selector");
    await click(".o-we-command");
    await animationFrame();
    await click(".o_records_selector_popover input");
    await animationFrame();
    // filtered using the domain
    expect(".o-autocomplete--dropdown-item").toHaveCount(2);
    await click(".o-autocomplete--dropdown-item:contains('Bob')");
    await animationFrame();
    await click(".o_records_selector_popover input");
    await animationFrame();
    expect(".o-autocomplete--dropdown-item").toHaveCount(1);
    await click(".o-autocomplete--dropdown-item:contains('Patrick')");
    await animationFrame();
    await click(".o_records_selector_popover .btn-primary");
    await animationFrame();
    await click(document.body);
    expect(updatePromptVal).toBe(
        '<p>Hello <span data-ai-record-id="1" data-oe-protected="true">Bob</span>, <span data-ai-record-id="2" data-oe-protected="true">Patrick</span>&nbsp;</p>',
    );
    // clicking on the record should reopen the field selector
    await click("div.o_ai_prompt span[data-ai-record-id]");
    await animationFrame();
    expect(".o_records_selector_popover").toHaveCount(1);
});

test("AI Prompt - Invalid records", async () => {
    await mountWithCleanup(AiPrompt, {
        props: {
            comodel: "dummy",
            model: "dummy",
            updatePrompt: () => {},
            prompt: '<p>Hello <span data-oe-protected data-ai-record-id="5">Larry</span></p>',
        },
    });
    expect(".o_ai_prompt").toHaveText("Hello Invalid Record");
});

test("does not call rpc on every keystroke", async () => {
    class AI extends models.Model {
        _name = "ai.agent";
    }
    defineModels([AI]);

    onRpc("ai.agent", "get_ask_ai_agent", () => {
        expect.step("get_ask_ai_agent");
        return { id: 1, name: "ASK AI" };
    });

    await mountWithCleanup(MainComponentsContainer);

    await press(["Control", "k"]);
    await animationFrame();

    await press("/");
    await animationFrame();

    await press("a");
    await animationFrame();

    expect.verifySteps(["get_ask_ai_agent"]);
});
