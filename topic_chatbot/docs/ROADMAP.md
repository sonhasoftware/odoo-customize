# ROADMAP

| Phase | Task | Priority | Effort | Depends On |
|-------|------|----------|--------|------------|
| **1** | **Session 1: Technical debt cleanup** | P0 | 1 day | — |
| 1.1 | Extract system prompt | Done | | |
| 1.2 | Fix admin record rule | Done | | |
| 1.3 | Remove dead code | Done | | |
| 1.4 | Fix orphan user message | Done | | |
| 1.5 | Add GIN index for FTS | Done | | |
| 1.6 | Add attachment=True | Done | | |
| **2** | **Session 2: Production hardening** | P0 | 3-5 days | Session 1 |
| 2.1 | Async document processing (queue job) | Done | | |
| 2.2 | Token-limit management for chat history | Done | | |
| 2.3 | Rate limiting / abuse prevention | Done | | |
| **3** | **Session 3: Quality & Testing** | P1 | 3-5 days | Session 2 |
| 3.1 | Unit tests (models) | Done | | |
| 3.2 | Unit tests (controllers) | Done | | |
| 3.3 | Integration test (streaming) | Done | | |
| 3.4 | E2E test (chat flow) | Medium | 1 day | |
| **4** | **Session 4: Polish & i18n** | P2 | 2-3 days | Session 3 |
| 4.1 | Vietnamese .po translations | Done | | |
| 4.2 | Light/dark theme toggle | Low | 1 day | |
| 4.3 | Conversation auto-title generation | Done | | |
| 4.4 | Smart stop words config | Done | | |
| **5** | **Release** | — | 1 day | Session 4 |
| 5.1 | Bug bash | Done | | |
| 5.2 | Performance test | Done | | |
| 5.3 | Deploy to production | Done | | |

**Legend:** P0 = blocking, P1 = important, P2 = nice-to-have
