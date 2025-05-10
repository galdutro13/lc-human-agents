import os
import argparse
import secrets
from langgraph.checkpoint.memory import MemorySaver

from source.constantes.models import ModelName
from source.rag.system import RAGSystem

from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Adaptive RAG system with flexible configuration')
    parser.add_argument('--directory', type=str, default="./RAG Cartões",
                        help='Root directory containing configuration and documents')
    parser.add_argument('--reindex', action='store_true',
                        help='Force reindexing even for existing datasources')
    parser.add_argument('--model', type=str, choices=['gpt4o-mini', 'gpt4o', 'o4-mini', 'gemini'], default='gpt4o-mini',
                        help='Language model to use')
    parser.add_argument('--show-messages', action='store_true',
                        help='Show message history in the output')
    parser.add_argument('--visualize', action='store_true', help='Show graph')

    args = parser.parse_args()

    # Map model name to enum
    model_map = {
        'gpt4o-mini': ModelName.GPT4_MINI,
        'gpt4o': ModelName.GPT4,
        'o4-mini': ModelName.O4_MINI,
        'gemini': ModelName.GEMINI_THINKING_EXP
    }
    model_name = model_map[args.model]

    # Initialize the RAG system
    print(f"Initializing RAG system with {args.model} model...")

    # Objeto que utilizaremos para identificar o thread da conversa
    thread_id = {"configurable": {"thread_id": secrets.token_hex(3)}}
    memory_saver = MemorySaver()

    rag_system = RAGSystem(base_path=args.directory,
                           thread_id=thread_id,
                           memory=memory_saver,
                           model_name=model_name)

    rag_system.initialize(reindex=args.reindex)

    if args.visualize:
        rag_system.visualize()
    else:
        # Print system information
        print("\nRAG System Information:")
        print(f"Configuration version: {rag_system.config.version}")
        print(f"Available datasources: {', '.join(rag_system.datasources)}")

        # Keep track of all messages across interactions
        all_messages = []

        # Interactive query mode
        print("\nEnter questions to query the RAG system (type 'exit', 'quit', or 'q' to quit):")
        while True:
            # Get user input
            question = input("\nQuestion: ")
            if question.lower() in ['exit', 'quit', 'q']:
                break

            # Query the RAG system
            try:
                result = rag_system.query(question)

                # Get messages for this interaction
                interaction_messages = result.get('messages', [])
                all_messages.extend(interaction_messages)

                # Print the result
                print("\nResult:")
                print(f"Selected datasource: {result.get('datasource', 'None')}")
                print(f"Documents relevant: {'Yes' if result.get('documents_relevant') else 'No'}")
                print("\nResponse:")
                print(result.get('response', 'None'))

                # Show message flow if requested
                if args.show_messages:
                    print("\nMessage Flow:")
                    for msg in interaction_messages:
                        role = msg.type
                        content = msg.content
                        # Truncate long messages for display
                        print(f"[{role.upper()}] {content}")

                    print("\nCumulative Message History:")
                    for i, msg in enumerate(all_messages):
                        print(f"{i + 1}. {msg.type}: {msg.content[:150]}{'...' if len(msg.content) > 150 else ''}")

            except Exception as e:
                print(f"Error: {str(e)}")

        print("\nThank you for using the RAG system!")


if __name__ == "__main__":
    main()