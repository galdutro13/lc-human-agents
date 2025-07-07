# lc-human-agents

## Visão Geral

Este projeto tem como objetivo simular interações entre agentes humanos e chatbots em um ambiente bancário. Ele utiliza técnicas de Processamento de Linguagem Natural (PLN) e Aprendizado de Máquina (ML) para criar agentes com personalidades distintas e cenários realistas. O projeto é construído usando Python e diversas bibliotecas de código aberto, como LangChain, LangGraph, Streamlit, e Google Generative AI.

## Técnicas Importantes

### LangChain

[LangChain](https://python.langchain.com/docs/get_started/introduction) é uma estrutura para o desenvolvimento de aplicações que utilizam modelos de linguagem. Ela fornece uma interface padrão para cadeias, integrações com várias ferramentas e implementações de ponta a ponta para cadeias comuns. Neste projeto, LangChain é usado para criar e gerenciar os modelos de linguagem que dirigem os agentes humanos e chatbots.

### LangGraph

[LangGraph](https://python.langchain.com/docs/langgraph) estende a biblioteca LangChain para suportar a criação de aplicações de agente multi-ator e cíclicas. É usado para gerenciar o fluxo de conversas e manter o estado das interações.

### Streamlit

[Streamlit](https://streamlit.io/) é uma biblioteca de código aberto que permite a criação de aplicações web interativas para visualização de dados e aprendizado de máquina. Neste projeto, Streamlit é usado para criar uma interface de usuário para visualizar as interações entre agentes humanos e chatbots.


## Estrutura do Projeto

```
lc-human-agents/
├── data/
│   └── extracted/
├── source/
│   ├── chat_graph/
│   ├── constantes/
│   ├── persona/
│   ├── prompt_manager/
│   │   └── constantes/
│   ├── scripts/
│   └── tests/
│       ├── chatbotserver_test/
│       ├── chatbot_test/
│       ├── integratio_test/
│       └── unittest/
└── tools/
    ├── db_work/
    ├── prompt_generation/
    └── visualizador_interacoes/
        ├── backend/
        └── frontend/
```

### **source/**

* #### **chat_graph/**
    Núcleo da construção e gerenciamento dos fluxos de conversa do chatbot. Ele é composto por `llms.py`, que carrega os modelos de linguagem; `workflow_builder.py`, que utiliza `StateGraph` para construir a estrutura da conversa; e `chat_function.py`, que define as classes abstratas e concretas para as funções executadas em cada nó do grafo de conversação.
* #### **constantes/**
    Centraliza as constantes utilizadas no projeto. Ele inclui `hiper_parametros.py`, que define os hiperparâmetros dos modelos, como temperatura e penalidades, e `models.py`, que enumera os diferentes modelos de linguagem disponíveis para uso no sistema.

* #### **persona/**
    Responsável por definir e gerenciar as personas dos usuários que interagem com o chatbot. Ele contém `persona.py`, que define a classe `Persona`; `persona_state.py`, que gerencia o estado da persona no fluxo de trabalho; `persona_function.py`, que implementa a função de chat específica para a persona; e `persona_workflow_builder.py`, que constrói os fluxos de trabalho específicos para cada persona.

* #### **rag/**
    Implementa o sistema de Retrieval-Augmented Generation (RAG). Ele é composto por vários submódulos: `config` para o gerenciamento de configurações, `document` para o carregamento e processamento de documentos, `functions` para as diferentes funções do RAG (roteador, classificador, recuperador, etc.), `logging` para o registro detalhado do processo RAG, `state` para o estado do fluxo de trabalho RAG, `system` para a fachada principal do sistema RAG, `vectorstore` para o gerenciamento de vector stores, e `workflow` para a construção do fluxo de trabalho RAG.

* #### **tests/**
    Este módulo abriga todos os testes do projeto. Ele está dividido em `unittest` para testes unitários de módulos individuais e `integratio_test` para testar a integração entre os diferentes componentes do sistema. Além disso, o diretório `chatbot_test` contém a implementação do mecanismo de interação entre as personas e o chatbot.

### **tools/**

* #### **bancobot_service/**
    Esta ferramenta implementa o serviço de backend para o chatbot do banco. Utilizando FastAPI, ela cria uma API RESTful que permite que múltiplos bots de usuário interajam com o bot do banco. O arquivo `banco_service.py` define os endpoints da API e gerencia as sessões de usuário, enquanto `start_banco_service.py` é o script utilizado para iniciar o serviço.

* #### **enxame_usuario/**
    Esta ferramenta é utilizada para simular a interação de múltiplos usuários com o bot do banco simultaneamente. O script principal, `start_usuarios.py`, lança um "enxame" de bots de usuário, cada um com sua própria persona e comportamento, com o objetivo de testar o bot do banco sob carga e em diferentes cenários de uso.

* #### **visualizador_interacoes/**
    Esta ferramenta oferece uma interface web para a visualização das interações entre os bots de usuário e o bot do banco. Ela é composta por um `backend` desenvolvido com FastAPI (`main.py`), que fornece os dados das conversas, e um `frontend` construído com Streamlit (`st_frontend.py`), que exibe o histórico de interações.

## Como Usar

### Pré-requisitos

*   Python 3.11 ou superior
*   Uma chave de API da OpenAI
*   Uma chave de API do Google AI

### Configuração

1. Clone o repositório:

    ```bash
    git clone <repository_url>
    ```

2. Crie um ambiente virtual e ative-o:

    ```bash
    cd lc-human-agents
    python -m venv venv
    source venv/bin/activate  # No Windows use: venv\Scripts\activate
    ```
3. Instale as dependências:

    ```bash
    pip install -r requirements.txt
    ```

    > **Atenção:** Caso ocorra algum erro relacionado à instalação do `chromadb`, verifique se você possui o `gcc` e as dependências de build do Python instaladas no seu sistema. No Windows, recomenda-se instalar o [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/). Consulte a [documentação oficial do chromadb](https://docs.trychroma.com/troubleshooting) para mais detalhes sobre troubleshooting.

4. Configure as variáveis de ambiente para as chaves de API da OpenAI e do Google AI:

    ```bash
    export OPENAI_API_KEY="your_openai_api_key"
    export GOOGLE_API_KEY="your_google_api_key"
    ```

### Executando os Testes

*   Para executar os testes unitários:

    ```bash
    python -m unittest discover source/tests/unittest
    ```
*   Para executar os testes de integração:

    ```bash
    python -m unittest discover source/tests/integratio_test
    ```

### Executando os Chatbots

1. Execute o script principal para iniciar a interação entre os chatbots:

    ```bash
    python source/tests/chatbot_test/main.py
    ```

### Executando o Visualizador de Interações

1. Inicie o backend FastAPI:

    ```bash
    cd tools/visualizador_interacoes/backend
    uvicorn main:app --reload
    ```
2. Inicie o frontend Streamlit em uma nova janela de terminal:

    ```bash
    cd tools/visualizador_interacoes/frontend
    streamlit run st_frontend.py
    ```
3. Acesse o visualizador de interações em seu navegador, normalmente em `http://localhost:8501`.

### Gerando Prompts

1. Configure o banco de dados:

    ```bash
    python tools/db_work/setup_db_cenarios.py
    ```
2. Insira dados de cenários e personas:

    ```bash
    python tools/db_work/insert_cenario&persona.py
    ```
3. Gere as missões:

    ```bash
    python tools/db_work/gerar_missoes.py
    ```
4. Gere os prompts:

```bash
python tools/prompt_generation/prompt_generator.py
```
