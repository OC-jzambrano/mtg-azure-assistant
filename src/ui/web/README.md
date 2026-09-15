# Standalone MTG Tutor

Run from the repository root:

```powershell
rtk proxy python -m uvicorn src.api.app:app --reload --port 8001
```

Open http://localhost:8001/chat/. FastAPI serves both the frontend and the API.
No Node build, Odoo installation or WebSocket server is required.

The left sidebar supports new chats, active chat selection and history search.
On mobile the Conversations button opens the sidebar. The Island illustration in
`assets/island.jpg` is a Magic: The Gathering card art crop retrieved through
Scryfall's named-card image endpoint (Wizards of the Coast card artwork).

## Reused source

The files in `vendor/` were copied from
`Odoo-Concept/odoo-tutor/odoo_tutor/static/`:

- `lib/nlux/umd/nlux-core.js`
- `lib/nlux/theme/nova.css`
- `src/webclient/sidebar/ai_sidebar.css`
- `images/iabotv2.png`

`app.js` replaces OWL lifecycle and Odoo RPC services with the original NLUX
builder and a batch adapter for `/api/chat`. `standalone.css` provides the layout
previously supplied by Odoo/Bootstrap. The sidebar stylesheet uses the MTG green palette (#386b60).

Conversation history, feedback and theme are stored in this browser's localStorage.
Cards and sources come from the API. Cards appear inline with their assistant response,
including restored conversations; sources remain in a separate collapsible section. Backend conversation memory retains its own
lifetime; local history is not replayed into backend memory after a server restart.
Exercise validation, ERP DOM recording and Odoo context hooks are not applicable
to this standalone chat and are not exposed as working controls.
