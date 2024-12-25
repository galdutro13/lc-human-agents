# chatbot.py
import secrets
from threading import RLock

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_openai import ChatOpenAI

from source.prompt_manager.base import CustomSystemPromptStrategy
from source.chat_graph import ModelName, ClassicChatFunction, ClassicWorkflowBuilder, get_llm

# Import the shared DB connection and lock
from source.tests.chatbotserver_test.shared_data import db_connection, db_lock


class ChatBotBase:
    def __init__(self, model_name, system_message, use_sqlitesaver=False, thread_id=None):
        self.model_name = model_name
        self.system_message = system_message
        self.thread_id = thread_id or secrets.token_hex(3)
        self.app = None
        self.config = None

        if use_sqlitesaver:
            self.initialize_with_sqlitesaver()
        else:
            self.initialize()

    def initialize(self):
        """Initialize with an in-memory memory saver."""
        self.model = get_llm(ModelName.GEMINI_THINKING_EXP)
        self.prompt = CustomSystemPromptStrategy(prompt_template=self.system_message).generate_prompt()

        self.app = ClassicWorkflowBuilder().build_classic_workflow(
            node_name="model",
            function=ClassicChatFunction(model=self.model, prompt=self.prompt),
            memory=MemorySaver()
        )

        self.config = {"configurable": {"thread_id": self.thread_id}}

    def initialize_with_sqlitesaver(self):
        """
        Initialize with a SqliteSaver, ensuring any write operations
        are locked for concurrency control.
        """
        with db_lock:
            self.model = get_llm(ModelName.GEMINI_THINKING_EXP)
            self.prompt = CustomSystemPromptStrategy(prompt_template=self.system_message).generate_prompt()

            self.app = ClassicWorkflowBuilder().build_classic_workflow(
                node_name="model",
                function=ClassicChatFunction(model=self.model, prompt=self.prompt),
                memory=SqliteSaver(conn=db_connection)
            )

            self.config = {"configurable": {"thread_id": self.thread_id}}

    def process_query(self, query: str) -> str:
        """
        Processes a query by passing it into the workflow app.
        The last message in the returned messages is the output.
        """
        with db_lock:  # concurrency protection
            input_messages = [HumanMessage(query)]
            output = self.app.invoke({"messages": input_messages}, self.config)
        output_message = output["messages"][-1]
        return output_message.content
