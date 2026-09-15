import logging
import sys
from pathlib import Path
from uuid import uuid4

import streamlit as st

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.ui.api_client import MTGAssistantClient

st.set_page_config(page_title="MTG Tutor", page_icon=":material/auto_awesome:", layout="wide")
st.html(Path(__file__).with_name("tutor.css"))

SUGGESTIONS = {
    "Maná": "¿Cómo funciona el maná?",
    "Fases del turno": "¿Qué fases hay en un turno?",
    "Buscar cartas": "Busco una carta blanca de coste inferior a dos de maná que sea guerrero",
    "Crear una carta": "Diseña una carta personalizada de un mago azul de coste tres",
}
TYPE_LABELS = {
    "rules": "Reglamento", "card_search": "Cartas",
    "custom_card": "Carta personalizada", "conversation": "Conversación",
}


def reset_conversation():
    if st.session_state.get("messages"):
        st.session_state.setdefault("conversations", {})[st.session_state.conversation_id] = {
            "messages": st.session_state.messages,
            "failed_prompt": st.session_state.get("failed_prompt"),
            "notes": st.session_state.get("work_notes", ""),
        }
    for key in list(st.session_state):
        if key.startswith(("feedback_", "suggestion_")):
            del st.session_state[key]
    st.session_state.messages = []
    st.session_state.conversation_id = str(uuid4())
    st.session_state.failed_prompt = None
    st.session_state.work_notes = ""


def open_conversation(conversation_id):
    reset_conversation()
    saved = st.session_state.conversations[conversation_id]
    st.session_state.conversation_id = conversation_id
    st.session_state.messages = saved["messages"]
    st.session_state.failed_prompt = saved["failed_prompt"]
    st.session_state.work_notes = saved.get("notes", "")


def render_message(message, index):
    with st.chat_message(message["role"]):
        if message.get("type"):
            st.caption(TYPE_LABELS.get(message["type"], "Respuesta"))
        st.markdown(message["content"])
        cards = message.get("cards") or []
        if cards:
            with st.container(horizontal=True):
                for card in cards:
                    with st.container(width=220, border=True):
                        image_url = card.get("image_url") or ""
                        if image_url.startswith(("https://", "http://")):
                            st.image(image_url, width="stretch")
                        st.markdown(f"**{card.get('name', 'Carta')}**")
                        st.caption(card.get("mana_cost") or "Sin coste de maná")
                        st.write(card.get("type_line") or "")
        sources = message.get("sources") or []
        if sources:
            with st.expander(f"Fuentes · {len(sources)}", icon=":material/menu_book:"):
                for source in sources:
                    st.write(source.get("title") or source.get("kind", "Fuente"))
                    if source.get("reference"):
                        st.caption(source["reference"])
        if message["role"] == "assistant":
            with st.container(horizontal=True, vertical_alignment="center"):
                st.feedback("thumbs", key=f"feedback_{st.session_state.conversation_id}_{index}")
                st.download_button(
                    "", message["content"], file_name="respuesta-mtg.md",
                    mime="text/markdown", icon=":material/download:",
                    help="Descargar respuesta", key=f"download_{index}", on_click="ignore",
                )


if "api_client" not in st.session_state:
    st.session_state.api_client = MTGAssistantClient()
if "conversation_id" not in st.session_state:
    reset_conversation()
if "failed_prompt" not in st.session_state:
    st.session_state.failed_prompt = None
st.session_state.setdefault("conversations", {})

with st.sidebar:
    st.subheader(":material/auto_awesome: MTG Tutor")
    st.caption("MAGIC: THE GATHERING")
    st.button("Nueva conversación", icon=":material/add_comment:", on_click=reset_conversation, width="stretch", type="primary")
    st.markdown("**Recientes**")
    for cid, saved in reversed(list(st.session_state.conversations.items())):
        title = next((m["content"] for m in saved["messages"] if m["role"] == "user"), "Conversación")
        st.button(title[:55], key=f"session_{cid}", icon=":material/chat_bubble_outline:", on_click=open_conversation, args=(cid,), width="stretch", disabled=cid == st.session_state.conversation_id)
    if not st.session_state.conversations:
        st.caption("Todavía no hay conversaciones anteriores")
    st.divider()
    st.caption("CONVERSACIÓN ACTUAL")
    st.write(f"{sum(m['role'] == 'user' for m in st.session_state.messages)} consultas")
    filters = next((m.get("active_filters") for m in reversed(st.session_state.messages) if m["role"] == "assistant"), None)
    if filters:
        st.markdown("**Filtros de búsqueda**")
        for name, value in filters.items():
            if value is not None and value != [] and value != "":
                st.text(f"{name}: {value}")
    st.divider()
    transcript = "\n\n".join(f"## {'Tú' if m['role'] == 'user' else 'MTG Tutor'}\n\n{m['content']}" for m in st.session_state.messages)
    st.download_button("Exportar conversación", transcript, "conversacion-mtg.md", "text/markdown", icon=":material/download:", disabled=not transcript, width="stretch", on_click="ignore")

with st.container(horizontal=True, vertical_alignment="center"):
    st.subheader(":material/auto_awesome: MTG Tutor")
    st.button("", icon=":material/restart_alt:", help="Reiniciar conversación", on_click=reset_conversation)
st.caption("MESA DE CONSULTA  /  REGLAS Y CARTAS")
st.divider()

chat_tab, library_tab, notes_tab = st.tabs([":material/forum: Conversación", ":material/style: Cartas y fuentes", ":material/edit_note: Notas"])
with library_tab:
    st.subheader("Material de la conversación")
    library_messages = [m for m in st.session_state.messages if m.get("cards") or m.get("sources")]
    if not library_messages:
        st.info("Aún no hay cartas ni referencias en esta conversación.", icon=":material/menu_book:")
    for i, message in enumerate(library_messages):
        for card in message.get("cards") or []:
            with st.container(horizontal=True):
                if (card.get("image_url") or "").startswith(("https://", "http://")):
                    st.image(card["image_url"], width=180)
                with st.container():
                    st.subheader(card.get("name", "Carta"))
                    st.write(card.get("mana_cost") or "")
                    st.write(card.get("type_line") or "")
            st.divider()
        for source in message.get("sources") or []:
            st.write(source.get("title") or "Fuente")
            st.caption(source.get("reference") or "")
with notes_tab:
    st.subheader("Notas de la consulta")
    notes = st.text_area("Notas", key="work_notes", height=300, label_visibility="collapsed", placeholder="Resolución, cartas pendientes, detalles de la partida…")
    st.download_button("Descargar notas", notes, "notas-mtg.txt", icon=":material/download:", on_click="ignore")

with chat_tab:
    chat_area = st.container(height=480, border=False, autoscroll=bool(st.session_state.messages), key="conversation")

with chat_area:
    if not st.session_state.messages:
        with st.chat_message("assistant", avatar=":material/auto_awesome:"):
            st.markdown("### Vamos a resolver tu próxima jugada")
            st.write("¿Qué ha ocurrido en la mesa? Cuéntame la situación o dime qué carta estás buscando.")

prompt = None
if not st.session_state.messages:
    with chat_area:
        st.caption("EMPEZAR UNA CONSULTA")
        selected = None
        icons = ["menu_book", "schedule", "search", "auto_fix_high"]
        with st.container(horizontal=True, key="suggestions"):
            for (label, example), icon in zip(SUGGESTIONS.items(), icons):
                with st.container(width=230, height=200, border=True):
                    st.markdown(f":material/{icon}: **{label}**")
                    st.caption(example)
                    if st.button("", icon=":material/arrow_forward:", help=example, key=f"suggestion_{label}"):
                        selected = label
    if selected:
        prompt = SUGGESTIONS[selected]

for index, message in enumerate(st.session_state.messages):
    with chat_area:
        render_message(message, index)

retry = False
if st.session_state.failed_prompt:
    st.error("No se pudo obtener la respuesta. Inténtalo de nuevo en unos momentos.")
    retry = st.button("Reintentar", icon=":material/refresh:")

with chat_tab:
    user_input = st.chat_input("Escribe tu consulta…", max_chars=4000, submit_mode="disable")
prompt = user_input or prompt
if retry:
    prompt = st.session_state.failed_prompt

if prompt and prompt.strip():
    if not retry:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with chat_area:
            render_message(st.session_state.messages[-1], len(st.session_state.messages) - 1)
    st.session_state.failed_prompt = None
    try:
        with st.status("Consultando…", type="compact"):
            data = st.session_state.api_client.chat(st.session_state.conversation_id, prompt)
        st.session_state.messages.append({
            "role": "assistant", "content": data["message"],
            "type": data.get("type"), "cards": data.get("cards") or [],
            "sources": data.get("sources") or [], "active_filters": data.get("active_filters"),
        })
    except Exception:
        logging.getLogger(__name__).exception("Chat request failed")
        st.session_state.failed_prompt = prompt
    st.rerun()
