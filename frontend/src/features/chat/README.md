# Chat feature (reserved)

This directory is a placeholder. The chat feature — the product surface of the
agent — is built in SPEC 2, not in this phase. See `docs/SPEC-2.md` section 9
for the UI requirements and section 9.1 for the architecture and conventions
that govern how it must be built.

## Reserved layout

When implemented, this feature follows a feature-based structure with a
hexagonal interior, as decided in `docs/SPEC-2.md` §9.1:

```
chat/
├── domain/           # Entities and value objects. No framework or IO.
├── application/      # Use cases and hooks (e.g. useChat). Orchestrates domain + gateway.
├── infrastructure/   # Adapters: HttpChatGateway (real), FakeChatGateway (test double).
├── ui/                # Components (ChatWindow, MessageList, ConfirmationCard, RoleSelector).
│                      # ui/ may not import infrastructure/ or @tanstack/react-query directly —
│                      # only hooks exposed by application/.
└── index.ts           # The feature's only public entry point.
```

Nothing outside `chat/` may import an internal path of `chat/` — only its
`index.ts`. This boundary is enforced by `eslint.config.js`.
