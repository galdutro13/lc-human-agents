import json
import uuid
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from source.prompt_manager.base import SystemPromptGenerator, CustomSystemPromptStrategy
from source.chat_graph import ModelName, ClassicChatFunction, ClassicWorkflowBuilder, get_openai_llm

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
        self.model: ChatOpenAI = get_openai_llm(ModelName.GPT4_MINI)
        self.prompt = CustomSystemPromptStrategy(prompt_template=self.system_message).generate_prompt()

        self.app = ClassicWorkflowBuilder().build_classic_workflow(
            node_name="model",
            function=ClassicChatFunction(model=self.model, prompt=self.prompt),
            memory=MemorySaver()
        )

        self.config = {"configurable": {"thread_id": self.thread_id}}

    def process_query(self, query, interaction_id=None, folder_name=""):
        input_messages = [HumanMessage(query)]
        output = self.app.invoke({"messages": input_messages}, self.config)
        output_message = output["messages"][-1]
        return output_message.content

