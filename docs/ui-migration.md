# MTG Tutor

The Odoo Tutor interaction pattern is adapted to native Streamlit widgets in
`src/ui/app_streamlit.py`. The frontend uses only `MTGAssistantClient` and the
existing FastAPI chat contract. Streamlit 1.63 or newer is required.

The interface includes conversation reset, initial suggestions, responsive card
results, source references, current filters, per-response downloads, conversation
export, session-local feedback and retry after a failed request. Feedback is not
persisted to the server. Retrying uses the same conversation ID; backend calls
are not idempotent, so a response lost after server processing may be repeated.

The workspace now uses the source tutor's muted mauve accent with green navigation,
a constrained reading width, a scrolling chat panel and separate tabs for collected
cards/sources and editable notes. Starting a new conversation retains the previous
one in the session sidebar, including notes and its backend conversation ID.
These conversations are session-local, not durable storage across browser reloads.
The scoped layout styles live in `src/ui/tutor.css`; global theme tokens live in
`.streamlit/config.toml`. Recheck the styles when upgrading Streamlit.

Odoo authentication, OWL services, DOM recorder, exercise validation and WebSocket
events are outside this migration. No Odoo server or assets are required.

Run the backend with `uvicorn src.api.app:app --port 8000` and the frontend with
`streamlit run src/ui/app_streamlit.py`. Set `BACKEND_URL` for a different backend.

Verify the frontend with `pytest tests/unit/test_chat_ui.py` and the HTTP contract
with `pytest tests/unit/test_api_contract.py`.
