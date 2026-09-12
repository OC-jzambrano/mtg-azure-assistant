import streamlit as st
import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.orchestrator import MTGOrchestrator

st.set_page_config(
    page_title="MTG Call Center AI Assistant",
    page_icon="🪄",
    layout="wide"
)

# Initialize Session State
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = MTGOrchestrator()

if "session_id" not in st.session_state:
    st.session_state.session_id = "streamlit-session-01"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "¡Hola! Soy tu asistente y juez de soporte para **Magic: The Gathering** del Call Center.\n\nPuedo resolver dudas del reglamento oficial (RAG), buscar cartas con imágenes en la API oficial, mantener el hilo de la conversación y diseñar cartas custom.",
            "sources": [],
            "cards": []
        }
    ]

# Sidebar
with st.sidebar:
    st.title("🪄 MTG AI Assistant")
    st.markdown("**Arquitectura Congelada (AGENT.md)**")
    st.info(
        "• **Frontend**: Streamlit\n\n"
        "• **API**: FastAPI\n\n"
        "• **Orchestrator**: 1 Router\n\n"
        "• **LLM**: Azure OpenAI\n\n"
        "• **RAG / Vector**: PostgreSQL + pgvector\n\n"
        "• **External Tool**: MTG REST API\n\n"
        "• **Memory**: Multi-turn Context"
    )
    st.divider()
    st.markdown("**4 Flujos del Reto:**")
    st.markdown(
        "1. 💧 **Rules RAG** (Maná / Fases / Combate)\n\n"
        "2. 🔍 **Card Search** (API MTG + Imágenes)\n\n"
        "3. 🔄 **Multi-turn** (Refinamiento elíptico)\n\n"
        "4. ⭐ **Custom Card** (Bonus Han Solo)"
    )
    
    if st.button("Reiniciar Conversación", use_container_width=True):
        st.session_state.messages = []
        st.session_state.session_id = f"streamlit-session-{int(st.session_state.get('reset_count', 0)) + 1}"
        st.session_state.reset_count = st.session_state.get("reset_count", 0) + 1
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
            st.markdown("**Cartas Encontradas:**")
            cols = st.columns(min(len(cards), 4))
            for idx, c in enumerate(cards[:4]):
                with cols[idx]:
                    if c.get("image_url"):
                        st.image(c["image_url"], caption=f"{c['name']} ({c.get('mana_cost', '')})", use_container_width=True)
                    else:
                        st.markdown(f"**{c['name']}**\n\nCoste: `{c.get('mana_cost', '')}`\nTipo: *{c.get('type_line', '')}*")
        
        # Display Sources / Citations if available
        sources = msg.get("sources", [])
        if sources:
            with st.expander("📚 Fuentes y Citaciones Oficiales de Reglas"):
                for s in sources:
                    st.markdown(f"- `{s}`")

# Handle user input (from text box or quick buttons)
user_input = st.chat_input("Escribe tu consulta sobre reglas o búsqueda de cartas...")
active_prompt = prompt_to_send or user_input

if active_prompt:
    st.session_state.messages.append({"role": "user", "content": active_prompt})
    
    with st.chat_message("user"):
        st.markdown(active_prompt)

    with st.chat_message("assistant"):
        with st.spinner("Consultando reglas y base de datos..."):
            response = st.session_state.orchestrator.handle_message(
                session_id=st.session_state.session_id,
                message=active_prompt
            )

        st.markdown(response["reply"])

        # Display Cards
        cards = response.get("cards", [])
        if cards:
            st.markdown("**Cartas Encontradas:**")
            cols = st.columns(min(len(cards), 4))
            for idx, c in enumerate(cards[:4]):
                with cols[idx]:
                    if c.get("image_url"):
                        st.image(c["image_url"], caption=f"{c['name']} ({c.get('mana_cost', '')})", use_container_width=True)
                    else:
                        st.markdown(f"**{c['name']}**\n\nCoste: `{c.get('mana_cost', '')}`\nTipo: *{c.get('type_line', '')}*")

        # Display Citations
        sources = response.get("sources", [])
        if sources:
            with st.expander("📚 Fuentes y Citaciones Oficiales de Reglas"):
                for s in sources:
                    st.markdown(f"- `{s}`")

    st.session_state.messages.append({
        "role": "assistant",
        "content": response["reply"],
        "sources": response.get("sources", []),
        "cards": response.get("cards", [])
    })
