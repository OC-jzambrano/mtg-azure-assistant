# MTG Tutor web interface

FastAPI serves the NLUX chat at `/chat/` from `src/ui/web/`. Start the application
with `rtk proxy python -m uvicorn src.api.app:app --port 8000` and open
http://localhost:8000/chat/. No separate frontend process is needed.

The interface uses the green navigation color (#386b60) for message bubbles,
submit controls, header actions and the selected conversation. Card images are
attached to their assistant response and remain visible in the chat history.
Source references remain in the collapsible “Fuentes” section, hidden when empty.

Conversation history, feedback and theme are saved in browser localStorage.
Older conversation records are supported by matching results to assistant replies
in order. Cards without an image URL display their name and card metadata.

The frontend continues to use the existing `/api/chat` JSON contract. Verify with
`rtk proxy python -m pytest tests/unit/test_web_frontend.py tests/unit/test_api_contract.py`.
