/* Standalone adapter for the original Odoo Tutor NLUX bundle. */
const $ = (selector) => document.querySelector(selector);
const storageKey = 'mtg-tutor-conversations-v1';
let sessions = [];
try { sessions = JSON.parse(localStorage.getItem(storageKey) || '[]'); } catch {}
if (!Array.isArray(sessions)) sessions = [];
sessions = sessions.filter(s => s && typeof s.id === 'string' && Array.isArray(s.messages));
let current = sessions[0] || fresh();
let chat;
let busy = false;
let dark = localStorage.getItem('mtg-tutor-theme') === 'dark';

function fresh() { return { id: crypto.randomUUID(), messages: [], results: [], votes: {} }; }
function persist() {
  sessions = [current, ...sessions.filter(s => s.id !== current.id)].slice(0, 30);
  try { localStorage.setItem(storageKey, JSON.stringify(sessions)); }
  catch { $('#error').hidden = false; $('#error').textContent = 'No se pudo guardar el historial en este navegador.'; }
  renderHistory();
}
function safeText(text) {
  return String(text).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}
function setBusy(value) {
  busy = value;
  for (const id of ['reset', 'theme', 'new-chat']) $(`#${id}`).disabled = value;
  renderHistory();
  $('#status').textContent = value ? 'Preparando respuesta…' : 'Listo para tu consulta';
}
async function batchText(message) {
  if (busy) throw new Error('Ya hay una consulta en curso');
  setBusy(true);
  $('#error').hidden = true;
  current.messages.push({ role: 'user', message: String(message) });
  persist();
  try {
    const response = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation_id: current.id, message: String(message) }),
      signal: AbortSignal.timeout(120000),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    if (typeof data.message !== 'string') throw new Error('Invalid response');
    current.messages.push({ role: 'assistant', message: data.message });
    (current.results ||= []).push(data);
    persist(); renderResources();
    return safeText(data.message);
  } catch {
    const text = 'No se pudo obtener una respuesta. Puedes volver a enviar tu consulta.';
    current.messages.push({ role: 'assistant', message: text });
    persist();
    return text;
  } finally { setBusy(false); }
}
function mount() {
  if (chat) chat.unmount();
  $('#offcanvasAiSidebar').classList.toggle('is-dark-theme', dark);
  chat = globalThis['@nlux/core'].createAiChat()
    .withAdapter({ batchText })
    .withDisplayOptions({ colorScheme: dark ? 'dark' : 'light' })
    .withConversationOptions({ historyPayloadSize: 'max', conversationStarters: [
      { prompt: '¿Cómo funciona el maná?' }, { prompt: 'Busco un guerrero blanco de coste uno' }, { prompt: 'Diseña una carta de un mago azul' },
    ] })
    .withComposerOptions({ placeholder: 'Escribe tu consulta sobre Magic…', autoFocus: true })
    .withPersonaOptions({ assistant: { name: 'MTG Tutor', avatar: 'assets/island.jpg', tagline: '¿Qué está pasando en tu partida?' }, user: { name: 'Tú' } })
    .withInitialConversation(current.messages.map(m => ({ role: m.role, message: safeText(m.message) })))
    .withMessageOptions({ waitTimeBeforeStreamCompletion: 'never' });
  chat.mount($('#chat-ui-container'));
  renderResources(); setBusy(false);
}
function renderResources() {
  const body = $('#resource-body'); body.replaceChildren();
  let count = 0;
  for (const result of current.results || []) {
    for (const card of result.cards || []) {
      const item = document.createElement('article'); item.className = 'result-card';
      if (/^https?:\/\//i.test(card.image_url || '')) {
        const img = document.createElement('img'); img.src = card.image_url; img.alt = card.name || 'Carta'; img.loading = 'lazy'; item.append(img);
      }
      const title = document.createElement('strong'); title.textContent = card.name; item.append(title);
      const detail = document.createElement('p'); detail.textContent = [card.mana_cost, card.type_line].filter(Boolean).join(' · '); item.append(detail);
      body.append(item); count++;
    }
    for (const source of result.sources || []) {
      const p = document.createElement('p'); p.className = 'source'; p.textContent = [source.title, source.reference].filter(Boolean).join(' · '); body.append(p); count++;
    }
  }
  $('#resource-count').textContent = count ? `(${count})` : '';
}
function renderHistory() {
  const list = $('#sessions'); list.replaceChildren();
  const query = $('#chat-search').value.toLocaleLowerCase();
  for (const session of [current, ...sessions.filter(s => s.id !== current.id)]) {
    if (query && !session.messages.some(m => String(m.message).toLocaleLowerCase().includes(query))) continue;
    const button = document.createElement('button'); button.textContent = session.messages.find(m => m.role === 'user')?.message || 'Nueva conversación';
    button.disabled = busy;
    button.classList.toggle('active', session.id === current.id);
    button.setAttribute('aria-current', String(session.id === current.id));
    button.title = button.textContent;
    button.onclick = () => { if (busy) return; current = session; persist(); $('#offcanvasAiSidebar').classList.remove('history-open'); mount(); };
    list.append(button);
  }
}
$('#reset').onclick = () => { persist(); current = fresh(); persist(); mount(); };
$('#new-chat').onclick = $('#reset').onclick;
$('#chat-search').oninput = renderHistory;
$('#theme').onclick = () => { dark = !dark; localStorage.setItem('mtg-tutor-theme', dark ? 'dark' : 'light'); mount(); };
$('#history-toggle').onclick = () => { $('#offcanvasAiSidebar').classList.toggle('history-open'); };
$('#export').onclick = () => {
  const blob = new Blob([current.messages.map(m => `## ${m.role === 'user' ? 'Tú' : 'MTG Tutor'}\n\n${m.message}`).join('\n\n')], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = 'conversacion-mtg.md'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
};
setInterval(() => {
  document.querySelectorAll('.nlux-comp-chatItem--received').forEach((item, index) => {
    if (item.querySelector('.message-tools')) return;
    const message = current.messages.filter(m => m.role === 'assistant')[index];
    if (!message) return;
    const actions = document.createElement('div'); actions.className = 'message-tools';
    for (const [label, symbol, vote] of [['Copiar respuesta', '⧉', null], ['Respuesta útil', '+', 1], ['Respuesta poco útil', '−', -1]]) {
      const button = document.createElement('button'); button.textContent = symbol; button.title = label; button.setAttribute('aria-label', label);
      if (vote) button.setAttribute('aria-pressed', String(current.votes?.[index] === vote));
      button.onclick = async () => {
        if (!vote) { try { await navigator.clipboard.writeText(message.message); button.textContent = '✓'; } catch { button.title = 'No se pudo copiar'; } return; }
        (current.votes ||= {})[index] = vote; persist();
        actions.querySelectorAll('[aria-pressed]').forEach(b => b.setAttribute('aria-pressed', String(b === button)));
      };
      actions.append(button);
    }
    item.append(actions);
  });
}, 1000);
mount();
fetch('/health').then(r => { $('#status').textContent = r.ok ? 'Conectado · Listo para tu consulta' : 'Servicio no disponible'; }).catch(() => { $('#status').textContent = 'Sin conexión'; });
