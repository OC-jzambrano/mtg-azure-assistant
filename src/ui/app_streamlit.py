import streamlit as st
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.ui.api_client import MTGAssistantClient

st.set_page_config(
    page_title="MTG Call Center AI Assistant",
    page_icon="🪄",
    layout="wide"
)

# Initialize API Client
if "api_client" not in st.session_state:
    st.session_state.api_client = MTGAssistantClient()

# Initialize unique conversation UUID (SPEC 06)
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = str(uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "¡Hola! Soy tu asistente y juez de soporte para **Magic: The Gathering** del Call Center.\n\nPuedo resolver dudas del reglamento oficial (RAG), buscar cartas con imágenes en la API oficial, mantener el hilo de la conversación y diseñar cartas custom.",
            "sources": [],
            "cards": [],
            "active_filters": None
        }
    ]

# Sidebar
with st.sidebar:
    st.title("🪄 MTG AI Assistant")
    st.caption("Frontend Streamlit conectado vía HTTP a FastAPI")
    st.markdown("**Arquitectura Limpia (SPEC 05)**")
    st.info(
        "• **Frontend**: Streamlit\n\n"
        "• **Protocolo**: HTTP / JSON\n\n"
        "• **Backend**: FastAPI (`/api/chat`)\n\n"
        "• **Orchestrator**: 1 Router (en backend)\n\n"
        "• **RAG / Memory**: Canonical Services"
    )
    st.divider()
    st.text(f"ID Sesión:\n{st.session_state.conversation_id[:18]}...")
    st.divider()
    
    if st.button("Reiniciar Conversación", use_container_width=True):
        st.session_state.messages = []
        st.session_state.conversation_id = str(uuid4())
        st.rerun()

# Main Header
st.title("🧙‍♂️ Asistente de Soporte para Magic: The Gathering")
st.caption("Call Center AI • Reglas Canónicas Oficiales • API magicthegathering.io • Citaciones CR")

# Quick Prompt Buttons
st.markdown("**Consultas rápidas de prueba:**")
col1, col2, col3, col4, col5 = st.columns(5)

prompt_to_send = None
with col1:
    if st.button("💧 Maná (CR 106)", use_container_width=True):
        prompt_to_send = "¿Cómo funciona el maná?"
with col2:
    if st.button("⏳ Fases Turno (CR 500)", use_container_width=True):
        prompt_to_send = "¿Qué fases hay en un turno?"
with col3:
    if st.button("⚔️ Rapaz + Ninja Ninjutsu", use_container_width=True):
        prompt_to_send = "Mi rapaz del campo de batalla ha hecho daño con su daña primero, si lo cambio con mi ninja de horas tardías ¿Aplico el daño?"
with col4:
    if st.button("🔍 Blanca guerrero < 2", use_container_width=True):
        prompt_to_send = "Busco una carta de color blanco de coste inferior a dos de mana que sea guerrero"
with col5:
    if st.button("🔄 ¿Y de coste uno?", use_container_width=True):
        prompt_to_send = "¿Y alguna que cueste solo uno?"

# Display Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Display Cards if available
        cards = msg.get("cards", [])
        if cards:
            st.markdown("**Cartas:**")
            cols = st.columns(min(len(cards), 4))
            for idx, c in enumerate(cards[:4]):
                with cols[idx]:
                    if c.get("image_url"):
                        st.image(c["image_url"], caption=f"{c['name']} ({c.get('mana_cost') or ''})", use_container_width=True)
                    else:
                        st.info(f"🃏 **{c['name']}**\n\n**Coste**: `{c.get('mana_cost') or '{0}'}`\n\n**Tipo**: *{c.get('type_line') or 'Desconocido'}*")
        
        # Display Sources / Citations if available
        sources = msg.get("sources", [])
        if sources:
            with st.expander("📚 Fuentes y Citaciones Oficiales"):
                for s in sources:
                    ref_str = f" ({s.get('reference')})" if s.get("reference") else ""
                    st.markdown(f"- **[{s.get('kind', '').upper()}]** {s.get('title')}{ref_str}")

# Handle user input
user_input = st.chat_input("Escribe tu consulta sobre reglas o búsqueda de cartas...")
active_prompt = prompt_to_send or user_input

if active_prompt:
    st.session_state.messages.append({"role": "user", "content": active_prompt})
    
    with st.chat_message("user"):
        st.markdown(active_prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando backend FastAPI..."):
            try:
                data = st.session_state.api_client.chat(
                    conversation_id=st.session_state.conversation_id,
                    message=active_prompt
                )
                bot_message = data.get("message", "")
                cards = data.get("cards", [])
                sources = data.get("sources", [])
                filters = data.get("active_filters")
            except Exception as e:
                bot_message = f"⚠️ Error al conectar con el backend FastAPI: {e}"
                cards = []
                sources = []
                filters = None

        st.markdown(bot_message)

        # Display Cards
        if cards:
            st.markdown("**Cartas:**")
            cols = st.columns(min(len(cards), 4))
            for idx, c in enumerate(cards[:4]):
                with cols[idx]:
                    if c.get("image_url"):
                        st.image(c["image_url"], caption=f"{c['name']} ({c.get('mana_cost') or ''})", use_container_width=True)
                    else:
                        st.info(f"🃏 **{c['name']}**\n\n**Coste**: `{c.get('mana_cost') or '{0}'}`\n\n**Tipo**: *{c.get('type_line') or 'Desconocido'}*")

        # Display Citations
        if sources:
            with st.expander("📚 Fuentes y Citaciones Oficiales"):
                for s in sources:
                    ref_str = f" ({s.get('reference')})" if s.get("reference") else ""
                    st.markdown(f"- **[{s.get('kind', '').upper()}]** {s.get('title')}{ref_str}")

    st.session_state.messages.append({
        "role": "assistant",
        "content": bot_message,
        "sources": sources,
        "cards": cards,
        "active_filters": filters
    })
