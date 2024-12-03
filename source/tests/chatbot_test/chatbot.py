import json
import uuid
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from source.prompt_manager.base import SystemPromptGenerator, CustomSystemPromptStrategy

def save_fields_to_json(output_message, interaction_id, folder_name):
    data = {
        "content": output_message.content,
        "response_metadata": output_message.additional_kwargs.get("response_metadata", {})
    }
    filename = f"dados/{folder_name}/data_{interaction_id}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


class ChatBotBase:
    def __init__(self, model_name, system_message, thread_id="abc123"):
        self.model = None
        self.prompt = None
        self.workflow = None
        self.model_name = model_name
        self.system_message = system_message
        self.thread_id = thread_id
        self.app = None
        self.config = None
        self.initialize()

    def initialize(self):
        self.model: ChatOpenAI = ChatOpenAI(model=self.model_name)
        genprompt = SystemPromptGenerator(strategy=CustomSystemPromptStrategy(prompt_template=self.system_message))
        self.prompt = genprompt.generate_prompt()
        self.workflow = self.build_workflow()
        self.app = self.initialize_app()
        self.config = {"configurable": {"thread_id": self.thread_id}}

    def build_workflow(self):
        workflow = StateGraph(state_schema=MessagesState)

        def call_model(state: MessagesState):
            chain = self.prompt | self.model
            response = chain.invoke(state)
            return {"messages": response}

        workflow.add_edge(START, "model")
        workflow.add_node("model", call_model)
        return workflow

    def initialize_app(self):
        memory = MemorySaver()
        return self.workflow.compile(checkpointer=memory)

    def process_query(self, query, interaction_id=None, folder_name=""):
        input_messages = [HumanMessage(query)]
        output = self.app.invoke({"messages": input_messages}, self.config)
        output_message = output["messages"][-1]
        # self.save_fields_to_json(output_message, interaction_id, folder_name)
        return output_message.content

