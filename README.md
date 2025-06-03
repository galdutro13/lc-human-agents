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

### Google Generative AI

[Google Generative AI](https://ai.google.dev/docs) é um conjunto de ferramentas e APIs que permitem aos desenvolvedores integrar modelos generativos de IA em suas aplicações. Neste projeto, ele é usado para gerar prompts para os agentes humanos e para alimentar os modelos de linguagem que dirigem os chatbots.

### SQLite

[SQLite](https://www.sqlite.org/docs.html) é um sistema de gerenciamento de banco de dados relacional (RDBMS) contido em uma biblioteca C. É um banco de dados leve, baseado em arquivo, que não requer um processo de servidor separado. Neste projeto, o SQLite é usado para armazenar e recuperar dados relacionados a cenários, personas, missões e interações.

## Tecnologias Utilizadas

*   **Python**: Linguagem de programação principal utilizada para o desenvolvimento do projeto.
*   **LangChain**: Framework para o desenvolvimento de aplicações que utilizam modelos de linguagem.
*   **LangGraph**: Biblioteca para a criação de aplicações de agente multi-ator e cíclicas.
*   **Streamlit**: Biblioteca para a criação de aplicações web interativas.
*   **FastAPI**: Framework web para a construção de APIs com Python.
*   **Google Generative AI**: Conjunto de ferramentas e APIs para integrar modelos generativos de IA em aplicações.
*   **SQLite**: Sistema de gerenciamento de banco de dados relacional baseado em arquivo.
*   **OpenAI**: Fornece acesso a modelos de linguagem como GPT-3 e GPT-4.
*   **LangChain Core**: Fornece componentes fundamentais para o LangChain.
*   **LangChain OpenAI**: Integração do LangChain com os modelos da OpenAI.
*   **LangChain Google GenAI**: Integração do LangChain com os modelos da Google Generative AI.

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

*   **data/**: Contém os dados utilizados no projeto, como arquivos CSV e JSON com informações sobre personas e cenários.
    *   **extracted/**: Contém arquivos JSON extraídos do arquivo `Personas.CSV`, cada um representando uma persona individual.
*   **source/**: Contém o código-fonte principal do projeto.
    *   **chat\_graph/**: Contém classes relacionadas ao grafo de chat e à construção do fluxo de trabalho.
    *   **constantes/**: Contém constantes como `TEMPERATURE`, `FREQUENCY_PENALTY`, e `PRESENCE_PENALTY` utilizadas na configuração dos modelos de linguagem.
    *   **persona/**: Contém a classe `Persona` para representar e manipular dados de personas.
    *   **prompt\_manager/**: Contém classes relacionadas à geração de prompts, incluindo estratégias e constantes para diferentes tipos de agentes.
        *   **constantes/**: Contém templates de prompts, como `template_padrao` e `template_agressivo`.
    *   **scripts/**: Contém scripts utilitários, como `csv_to_json.py` para converter dados de CSV para JSON.
    *   **tests/**: Contém testes unitários e de integração para o projeto.
        *   **chatbotserver\_test/**: Contém código para executar chatbots em servidores, como `server_usuario.py` e `server_banco.py`, e `chatbot.py` que é uma classe base para chatbots.
        *   **chatbot\_test/**: Contém classes para testar os chatbots, como `BancoBot` e `UsuarioBot`, e `chatbot.py` que é uma classe base para chatbots.
        *   **integratio\_test/**: Contém testes de integração para diferentes componentes, como `persona_csv_integration.py` e `workflow_integration_test.py`.
        *   **unittest/**: Contém testes unitários para módulos individuais, como `test_csv_to_json.py` e `test_prompt_manager.py`.
*   **tools/**: Contém ferramentas auxiliares para o projeto.
    *   **db\_work/**: Contém scripts para configurar e popular o banco de dados SQLite, como `setup_db_cenarios.py`, `insert_cenario&persona.py`, e `gerar_missoes.py`.
    *   **prompt\_generation/**: Contém scripts para geração de prompts usando modelos de linguagem, como `prompt_generator.py`, `get_generator_prompt.py` e `rate_limiter.py`.
    *   **visualizador\_interacoes/**: Contém código para uma aplicação Streamlit que visualiza as interações dos chatbots.
        *   **backend/**: Contém o código do servidor FastAPI que fornece os dados para o frontend, como `main.py`.
        *   **frontend/**: Contém o código do frontend Streamlit, como `st_frontend.py`.

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
2. Instale as dependências:

    ```bash
    cd lc-human-agents
    pip install -r requirements.txt
    ```
3. Configure as variáveis de ambiente para as chaves de API da OpenAI e do Google AI:

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
