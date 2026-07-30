# AI_RULES.md — Rules for AI-assisted development

## Code Quality
1. **No comments in code** — unless business-essential (e.g., regex explanation).
2. **DRY** — any duplication >3 lines must be extracted into a method/constant.
3. **No dead code** — unused methods/variables must be removed immediately.
4. **Security first** — never log API keys, never expose stack traces to users.
5. **Idiomatic Odoo** — use ORM, record rules, ACLs; avoid raw SQL unless necessary.

## Architecture
6. **No stored context-dependent fields** — `is_admin` type fields must remain non-stored computed.
7. **Async for heavy ops** — document parsing, chunking must go through queue (not web thread).
8. **Savepoints for multi-step writes** — when saving multiple records that depend on each other, wrap in `request.env.cr.savepoint()` or use error-tracking (flag + cleanup).

## Testing
9. **Every model needs a unit test** — test CRUD, constraints, and business logic.
10. **Every controller needs an integration test** — test auth, error cases, and happy path.
11. **Streaming endpoints need response-streaming tests** — verify SSE events are well-formed.

## Documentation
12. **Every session must produce:**
    - `SESSION_SUMMARY.md` — what was done
    - `DECISIONS.md` — why it was done that way
    - `ROADMAP.md` — what's next
    - `AI_RULES.md` — this file (evolving rules)
13. **ARCHITECTURE.md** must stay in sync with actual code structure.
