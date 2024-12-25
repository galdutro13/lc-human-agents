import streamlit as st
import requests
from datetime import datetime

# URL base do servidor FastAPI
BASE_URL = "http://localhost:8000"

# Carrega a lista de interações (thread_id e ts)
def load_interactions():
    response = requests.get(f"{BASE_URL}/interactions")
    response.raise_for_status()
    return response.json()

# Carrega a interação selecionada (mensagens)
def load_interaction(thread_id):
    response = requests.get(f"{BASE_URL}/interactions/{thread_id}")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()

# Configura a página
st.set_page_config(layout="wide", page_title="Visualizador de Interações")

# Estado para armazenar a conversa selecionada
if "selected_thread" not in st.session_state:
    st.session_state.selected_thread = None

# Estado para armazenar a lista de interações
if "interactions" not in st.session_state:
    try:
        st.session_state.interactions = load_interactions()
    except:
        st.session_state.interactions = []

# Função para formatar timestamp
def format_ts(ts):
    # Supondo que ts seja um string ISO 8601 (ex: "2024-12-10T23:02:41.783802+00:00")
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ts

##############################
# Sidebar
##############################
with st.sidebar:
    st.write("**Conversas**")
    for i, item in enumerate(st.session_state.interactions):
        ts_str = format_ts(item["ts"])
        if st.button(f"{ts_str}", key=f"conv_{i}"):
            st.session_state.selected_thread = item["thread_id"]

##############################
# Visualizador de Conversa
##############################
st.title("Visualizador de Interações")

if st.session_state.selected_thread is None:
    st.info("Nenhuma conversa selecionada. Por favor, escolha uma conversa na sidebar.")
else:
    # Carrega as mensagens da conversa selecionada
    conversation = load_interaction(st.session_state.selected_thread)
    if conversation is None or "messages" not in conversation:
        st.warning("Não foi possível carregar esta conversa ou ela está vazia.")
    else:
        messages = conversation["messages"]

        # Ajuste de estilo CSS para garantir espaçamento uniforme entre as mensagens
        # Usamos gap para o espaçamento vertical e removemos margens verticais individuais.
        st.markdown("""
        <style>
        .chat-container {
            display: flex;
            flex-direction: column;
            gap: 10px; /* Espaçamento vertical consistente entre as mensagens */
        }

        .human-bubble {
            background-color: #3a3a3a;
            color: white;
            padding: 10px;
            border-radius: 10px;
            max-width: 60%;
            word-wrap: break-word;
            margin-right: auto; /* Alinha à esquerda */
            margin-left: 0;     /* Sem margem lateral esquerda adicional */
        }

        .ai-bubble {
            background-color: #003366;
            color: white;
            padding: 10px;
            border-radius: 10px;
            max-width: 60%;
            word-wrap: break-word;
            margin-left: auto; /* Alinha à direita */
            margin-right: 0;   /* Sem margem lateral direita adicional */
        }
        </style>
        """, unsafe_allow_html=True)

        # Container para as mensagens
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for msg in messages:
            if msg["type"] == "human":
                st.markdown(f'<div class="human-bubble">{msg["content"]}</div>', unsafe_allow_html=True)
            elif msg["type"] == "ai":
                st.markdown(f'<div class="ai-bubble">{msg["content"]}</div>', unsafe_allow_html=True)
            else:
                # Caso 'other', se existir, trataremos como human para padronizar
                st.markdown(f'<div class="human-bubble">{msg["content"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
