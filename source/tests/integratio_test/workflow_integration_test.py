import unittest

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from langgraph.graph import MessagesState

from langgraph.graph import START, MessagesState, StateGraph

from source.prompt_manager import DefaultSystemPromptStrategy
from source.chat_graph import (
    ModelName,
    ClassicChatFunction,
    ClassicWorkflowBuilder,
    get_openai_llm,
)



class TestChatGraphPromptIntegration(unittest.TestCase):
    def test_initial(self):
        model_name = ModelName.GPT4_MINI
        model = get_openai_llm(model_name)
        prompt = DefaultSystemPromptStrategy().generate_prompt()

        def build_workflow():
            workflow = StateGraph(state_schema=MessagesState)

            def call_model(state: MessagesState):
                chain = prompt | model
                response = chain.invoke(state)
                return {"messages": response}

            workflow.add_edge(START, "model")
            workflow.add_node("model", call_model)
            return workflow

        app = build_workflow().compile()

        config = {"configurable": {"thread_id": "abc123"}}
        input_message = [HumanMessage("Hello, how are you?")]
        output = app.invoke({"messages": input_message})

        print(output["messages"][-1].content)


    def test_chat_function(self):
        model_name = ModelName.GPT4_MINI
        model = get_openai_llm(model_name)
        prompt = DefaultSystemPromptStrategy().generate_prompt()

        chat_function = ClassicChatFunction(model=model, prompt=prompt)

        def build_workflow():
            workflow = StateGraph(state_schema=MessagesState)

            workflow.add_edge(START, "model")
            workflow.add_node("model", chat_function)
            return workflow

        app = build_workflow().compile()
        config = {"configurable": {"thread_id": "abc123"}}
        input_message = [HumanMessage("Hello, how are you?")]
        output = app.invoke({"messages": input_message})

        print(output["messages"][-1].content)



    def test_default_workflow(self):
        """Test that the default workflow generates a prompt."""
        model_name = ModelName.GPT4_MINI
        model = get_openai_llm(model_name)
        prompt = DefaultSystemPromptStrategy().generate_prompt()

        chat_function = ClassicChatFunction(model=model, prompt=prompt)

        workflow_builder = ClassicWorkflowBuilder()
        workflow_builder.add_edge("model")
        workflow_builder.add_node("model", chat_function)
        app = workflow_builder.build_workflow()

        config = {"configurable": {"thread_id": "abc123"}}
        input_message = [HumanMessage("Hello, how are you?")]
        output = app.invoke({"messages": input_message}, config=config)

        print(output["messages"][-1].content)