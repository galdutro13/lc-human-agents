import streamlit as st
import requests
import threading
import time
import uvicorn  # Ensure that uvicorn is installed in your environment
from datetime import datetime
import sys
import os

# ------------------------------------------------------------------------------
# Backend Startup Section
# ------------------------------------------------------------------------------

# Define a function to add the project root to the Python path.
def get_project_root():
    # Calculate the project root directory by going three levels up:
    # st_frontend.py --> frontend --> visualizador_interacoes --> tools --> project root
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    print(f"Adding {project_root} to sys.path")
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Define a function to start the backend server using uvicorn.
def run_backend():
    # The module path reflects your folder structure.
    uvicorn.run("tools.visualizador_interacoes.backend.main:app",
                host="localhost", port=8000, log_level="info")

# Ensure that the backend is started only once even if Streamlit reruns the script.
if "backend_started" not in st.session_state:
    st.session_state.backend_started = False

if "configured_python_path" not in st.session_state:
    st.session_state.configured_python_path = False

# This ensures that the Python interpreter can locate the project's root directory.
if not st.session_state.configured_python_path:
    get_project_root()
    st.session_state.configured_python_path = True

# Start the backend server if it is not already running.
if not st.session_state.backend_started:
    # Start the backend in a daemon thread.
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    st.session_state.backend_started = True

    # Wait until the backend is responsive.
    backend_ready = False
    max_attempts = 20  # Number of attempts
    attempt = 0
    backend_url = "http://localhost:8000/interactions"
    while not backend_ready and attempt < max_attempts:
        try:
            response = requests.get(backend_url)
            if response.status_code == 200:
                backend_ready = True
                break
        except requests.exceptions.RequestException:
            # The backend might not be ready yet.
            time.sleep(0.5)
        attempt += 1

    if not backend_ready:
        st.error("O servidor backend não iniciou a tempo. Por favor, tente novamente.")
        st.stop()  # Stop further execution

# ------------------------------------------------------------------------------
# Rest of the Frontend (Streamlit) Code
# ------------------------------------------------------------------------------

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
# Header (Título + Botão de Download)
##############################
col1, col2 = st.columns([0.8, 0.2])

with col1:
    st.title("Visualizador de Interações")

# Somente mostra o botão se houver uma conversa selecionada
with col2:
    if st.session_state.selected_thread is not None:
        # Ao clicar neste botão, iremos buscar o arquivo Excel do backend
        # e em seguida exibiremos o st.download_button real.
        if st.button("Gerar Excel", type="primary"):
            try:
                # Faz a requisição para obter o conteúdo do Excel
                excel_url = f"{BASE_URL}/interactions/{st.session_state.selected_thread}/excel"
                response = requests.get(excel_url)
                response.raise_for_status()

                # Converte em bytes
                excel_data = response.content

                # Mostra imediatamente um botão de download
                st.download_button(
                    label="Baixar Excel",
                    data=excel_data,
                    file_name=f"conversa_{st.session_state.selected_thread}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            except Exception as e:
                st.error(f"Falha ao gerar ou baixar o Excel: {e}")

##############################
# Visualizador de Conversa
##############################
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
            margin-left: 0;
        }

        .ai-bubble {
            background-color: #003366;
            color: white;
            padding: 10px;
            border-radius: 10px;
            max-width: 60%;
            word-wrap: break-word;
            margin-left: auto; /* Alinha à direita */
            margin-right: 0;
        }
        </style>
        """, unsafe_allow_html=True)

        # Container para as mensagens
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for msg in messages:
            bubble_class = "human-bubble" if msg["type"] == "human" else "ai-bubble"
            st.markdown(f'<div class="{bubble_class}">{msg["content"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
