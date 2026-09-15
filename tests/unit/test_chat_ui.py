from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def test_chat_response_feedback_and_reset():
    app = AppTest.from_file("../../src/ui/app_streamlit.py").run()
    conversation_id = app.session_state.conversation_id
    response = {
        "message": "Una respuesta", "type": "card_search",
        "cards": [{"name": "Soldado", "image_url": None}],
        "sources": [{"title": "Reglas", "reference": "CR 106"}],
        "active_filters": {"colors": ["W"]},
    }
    with patch("src.ui.api_client.MTGAssistantClient.chat", return_value=response) as chat:
        app.chat_input[0].set_value("Busca un soldado").run()
        assert not app.exception
        chat.assert_called_once_with(conversation_id, "Busca un soldado")
        assert len(app.chat_message) == 2
        app.run()
        assert chat.call_count == 1
    next(button for button in app.button if button.label == "Nueva conversación").click().run()
    assert not app.exception
    assert app.session_state.messages == []
    assert app.session_state.conversation_id != conversation_id
    app.button(key=f"session_{conversation_id}").click().run()
    assert not app.exception
    assert app.session_state.conversation_id == conversation_id
    assert len(app.session_state.messages) == 2


def test_failed_request_can_retry_without_duplicate_user_message():
    app = AppTest.from_file("../../src/ui/app_streamlit.py").run()
    with patch("src.ui.api_client.MTGAssistantClient.chat", side_effect=ConnectionError("private details")):
        app.chat_input[0].set_value("Hola").run()
    assert not app.exception
    assert "private details" not in app.error[0].value
    with patch("src.ui.api_client.MTGAssistantClient.chat", return_value={"message": "Hola"}):
        next(button for button in app.button if button.label == "Reintentar").click().run()
    assert not app.exception
    assert len(app.session_state.messages) == 2
    assert app.session_state.failed_prompt is None
