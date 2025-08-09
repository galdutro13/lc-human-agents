# lc-human-agents

## Overview

This project aims to simulate interactions between "human" agents and chatbots in a banking environment. It uses the LangChain library to construct complex conversation flows, allowing multiple agents to interact with a banking chatbot. The system is designed to be extensible, enabling the addition of new personas and interaction scenarios.

As a proof of concept, we provide a set of 25 prompts defining 25 personas and their respective scenarios.

**The documentation used for RAG as well as the generated dialogues are not provided, as they contain sensitive information from a financial institution. Technical details about these artifacts can be obtained via email contact with the project team.**

These simulated interactions can be evaluated through the extraction of touchpoints. Touchpoints are points of contact between the dialogue and the goals of a conversation within the scope of a business process. In this project, for a specific domain, we provide an example set of touchpoints to be used as input for a language model to analyze the dialogue, interpret it, and extract one touchpoint per utterance. An example prompt for this task is also provided.

Furthermore, the proposed analysis for this evaluation is based on process mining. Thus, the instrumentation code to distribute the dialogue generation over time—simulating the runtime of a real system—as well as the code to generate the event log file required for this analysis, are also provided.

## Key Technologies

### LangChain

[LangChain](https://python.langchain.com/docs/get_started/introduction) is a framework for developing applications using language models. It provides a standard interface for chains, integrations with various tools, and end-to-end implementations for common chains. In this project, LangChain is used to create and manage the language models that drive both the human agents and the chatbots.

### LangGraph

[LangGraph](https://python.langchain.com/docs/langgraph) extends the LangChain library to support the creation of multi-actor and cyclic agent applications. It is used to manage the conversation flow and maintain the state of interactions.

### Streamlit

[Streamlit](https://streamlit.io/) is an open-source library that enables the creation of interactive web applications for data visualization and machine learning. In this project, Streamlit is used to create a user interface to visualize interactions between human agents and chatbots.

## Project Structure

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

* #### **chat\_graph/**

  Core of the chatbot conversation flow construction and management. It includes `llms.py` (loads language models), `workflow_builder.py` (uses `StateGraph` to build the conversation structure), and `chat_function.py` (defines abstract and concrete classes for functions executed at each graph node).

* #### **constantes/**

  Centralizes constants used in the project, including `hiper_parametros.py` (defines model hyperparameters like temperature and penalties) and `models.py` (enumerates available language models for use in the system).

* #### **persona/**

  Responsible for defining and managing user personas that interact with the chatbot. It contains `persona.py` (defines the `Persona` class), `persona_state.py` (manages persona state in the workflow), `persona_function.py` (implements the persona-specific chat function), and `persona_workflow_builder.py` (builds persona-specific workflows).

* #### **rag/**

  Implements the Retrieval-Augmented Generation (RAG) system. Comprises several submodules: `config` (configuration management), `document` (document loading and processing), `functions` (RAG functions such as router, classifier, retriever, etc.), `logging` (detailed RAG process logging), `state` (workflow state), `system` (main RAG system interface), `vectorstore` (vector store management), and `workflow` (workflow construction).

* #### **tests/**

  Contains all project tests. Divided into `unittest` for unit tests of individual modules and `integratio_test` for integration testing across components. The `chatbot_test` directory implements the interaction mechanism between personas and the chatbot.

### **tools/**

* #### **bancobot\_service/**

  Backend service implementation for the banking chatbot. Using FastAPI, it creates a RESTful API enabling multiple user bots to interact with the bank bot. The `banco_service.py` file defines the API endpoints and manages user sessions, while `start_banco_service.py` starts the service.

* #### **enxame\_usuario/**

  Simulates simultaneous interaction of multiple users with the bank bot. The main script, `start_usuarios.py`, launches a "swarm" of user bots, each with its own persona and behavior, aiming to test the bot under load and various usage scenarios.

* #### **visualizador\_interacoes/**

  Provides a web interface to visualize interactions between user bots and the bank bot. It includes a FastAPI `backend` (`main.py`) for providing conversation data and a Streamlit `frontend` (`st_frontend.py`) for displaying the interaction history.

## How to Use

### Prerequisites

* Python 3.11 or higher
* An OpenAI API key
* A Google AI API key

### Setup

1. Clone the repository:

   ```bash
   git clone <repository_url>
   ```

2. Create and activate a virtual environment:

   ```bash
   cd lc-human-agents
   python -m venv venv
   source venv/bin/activate # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   > **Note:** If an error occurs related to `chromadb` installation, ensure you have `gcc` and Python build dependencies installed on your system. On Windows, it's recommended to install [Build Tools for Visual Studio](https://visualstudio.microsoft.com/visual-cpp-build-tools/). Refer to the [chromadb documentation](https://docs.trychroma.com/troubleshooting) for troubleshooting.

4. Set environment variables for OpenAI and Google AI API keys:

   Add them to the `.env` file at the project root:

   ```bash
   OPENAI_API_KEY=your_openai_api_key
   GOOGLE_API_KEY=your_google_api_key
   ```

5. Set up and populate the datasources used for RAG:

   The "RAG Cartoes" folder contains a sample default configuration. You may use it as-is or edit it to suit your needs. Alternatively, you can create your own configuration.

### Running the Interaction Simulation

**Note:** Before running the simulation, make sure the following environment variables are set on both consoles:

```bash
export PYTHONUNBUFFERED=1 # $env:PYTHONUNBUFFERED="1" in PowerShell
export PYTHONPATH=$PWD # $env:PYTHONPATH=(Get-Location).Path in PowerShell
```

Then, start the bank chatbot service with the following command:

```bash
python ./tools/bancobot_service/start_banco_service.py
```

Once the bank chatbot service is running, you can simulate interactions with multiple users:

```bash
python ./tools/enxame_usuario/start_usuarios.py --prompts-file "<path_to_prompts_file>"
```

> **Note:** On first run, the RAG system will build the necessary vector stores. This may take time depending on data size and environment configuration.
> Therefore, we recommend running the script `source/tests/integratio_test/rag_test.py` beforehand to ensure vector stores are ready and the system operates correctly.
> Run it with:
>
> ```bash
> python source/tests/integratio_test/rag_test.py
> ```
>
> Inside the script, submit any prompt and wait for the chatbot's response.

### Running the Interaction Visualizer

**Note:** Before running the visualizer, ensure the following environment variables are set:

```bash
export PYTHONUNBUFFERED=1 # $env:PYTHONUNBUFFERED="1" in PowerShell
export PYTHONPATH=$PWD # $env:PYTHONPATH=(Get-Location).Path in PowerShell
```

Then run the following command to start the interaction visualizer:

```bash
python .\launch_simulador.py
```

### Running the Touchpoint Extractor

To extract touchpoints from interactions, first export them via the visualizer by clicking the "💾" button.
Then run the following command to start the touchpoint extractor:

```bash
python .\tools\touchpoints_extractor\touchpoint_classifier.py \
  --dialogue_json <exported_interactions_file> \
  --touchpoints_ai_json .\tools\touchpoints_extractor\Touchpoint_ai.json \
  --touchpoints_human_json .\tools\touchpoints_extractor\Touchpoint_human.json \
  --output_csv analises_todas.csv
```
