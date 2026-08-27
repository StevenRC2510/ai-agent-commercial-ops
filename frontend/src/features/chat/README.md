# Chat feature

The product surface of the agent, built per `docs/SPEC-2.md` §9 and §9.1.

## Layout

```
chat/
├── domain/           # Entities, value objects and the pure conversation transitions.
├── application/      # The ChatGateway port, the gateway context, and useChat.
├── infrastructure/   # Adapters: HttpChatGateway (real), FakeChatGateway (test double).
├── testing/          # Test wiring: the fake gateway inside the providers useChat needs.
├── ui/               # Components. ui/ may not import infrastructure/ or
│                     # @tanstack/react-query — only hooks exposed by application/.
└── index.ts          # The feature's only public entry point.
```

Nothing outside `chat/` may import an internal path of `chat/` — only its
`index.ts`. This boundary is enforced by `eslint.config.js`.

## The two decisions worth knowing before changing anything here

**Confirmation is out of band.** A `confirmation_required` turn puts a card on
screen and disables the composer. The user consents by pressing a button that
posts the opaque `pending_id` to `/confirm` — never by typing "sí". Consent is
therefore an authenticated HTTP event, not text the model could have produced
(`docs/adr/0002-out-of-band-write-confirmation.md`).

**`confirmAction` never retries.** `sendMessage` retries twice with backoff;
`confirmAction` retries zero times, because a retry after a write that did
happen would report a failure that did not (`docs/adr/0006-no-retry-on-confirmation.md`).
Both numbers live in `application/useChat.constants.ts` and are pinned by tests.

Agent text is rendered as text and only as text — no `dangerouslySetInnerHTML`
anywhere (SPEC-2 §9.3, pinned by `ui/Message/Message.test.tsx`).
