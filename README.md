# lc-human-agents

## Visão Geral

Este projeto tem como objetivo simular interações entre agentes humanos e chatbots em um ambiente bancário. Ele utiliza a biblioteca LangChain para construir fluxos de conversa complexos, permitindo que múltiplos agentes interajam com um chatbot bancário. O sistema é projetado para ser extensível, permitindo a adição de novas personas e cenários de interação.

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
   Ou insira as chaves no arquivo `.env` na raiz do projeto:

    ```bash
    OPENAI_API_KEY=your_openai_api_key
    GOOGLE_API_KEY=your_google_api_key
    ```
   
5. Configure e popule os datasources utilizados para o rag:

    Na pasta RAG Cartões está disponível um exemplo de configuração padrão. Você pode seguir com ele, e edita-lo. Ou então, cirar sua própria configuração.
   
### Executando a simulação de interações

**Atenção:** Antes de executar a simulação, certifique-se que as seguintes variáveis de ambiente estejam configuradas:

```bash
export PYTHONUNBUFFERED=1 # $env:PYTHONUNBUFFERED="1" no PowerShell
export PYTHONPATH=$PWD # $env:PYTHONPATH=(Get-Location).Path no PowerShell
```

Após isso, você deve executar o seguinte comando para iniciar o serviço do chatbot do banco:

```bash
python .\tools\bancobot_service\start_banco_service.py
```

Depois de iniciar o serviço do chatbot do banco, você pode executar a simulação de interações com múltiplos usuários. Para isso, utilize o seguinte comando:

```bash
python .\tools\enxame_usuario\start_usuarios.py --prompts-file "<caminho_para_o_arquivo_de_prompts>"
```

> **Atenção:** Na primeira execução do chatbot do banco, o RAG criará os vector stores necessários para o funcionamento do sistema. Isso pode levar algum tempo, dependendo do tamanho dos dados e da configuração do seu ambiente.
> Por isso recomendamos que você execute script `source/tests/integratio_test/rag_test.py` antes de iniciar a simulação de interações. Isso garantirá que os vector stores estejam prontos e que o sistema funcione corretamente.
> Você pode executa-lo com o seguinte comando:
> ```bash
> python source/tests/integratio_test/rag_test.py
> ```
> Dentro desse script, você deve enviar um prompt qualquer. Após isso, aguarde até a geração da resposta do chatbot.

### Executando o Visualizador de Interações

**Atenção:** Antes de executar o visualizador, certifique-se que as seguintes variáveis de ambiente estejam configuradas:

```bash
export PYTHONUNBUFFERED=1 # $env:PYTHONUNBUFFERED="1" no PowerShell
export PYTHONPATH=$PWD # $env:PYTHONPATH=(Get-Location).Path no PowerShell
```

Após isso, você deve executar o seguinte comando para iniciar o visualizador de interações:

```bash
python .\launch_simulador.py
```

### Executar o extrator de touchpoints
Para extrair os touchpoints das interações, você primeiro deve exporta-las através do visualizador de interações. Você pode fazer isso clicando no botão "💾".
Após isso, você pode executar o seguinte comando para iniciar o extrator de touchpoints:

```bash
python touchpoint_classifier.py \
  --dialogue_json <interações_exportadas_pelo_visualizador> \
  --touchpoints_ai_json Touchpoint_ai.json \
  --touchpoints_human_json Touchpoint_human.json \
  --output_csv analises_todas.csv
```