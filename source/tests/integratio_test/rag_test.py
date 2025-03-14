import os
import argparse
from source.chat_graph.models import ModelName
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
    parser.add_argument('--model', type=str, choices=['gpt4o-mini', 'gpt4o'], default='gpt4o-mini',
                        help='Language model to use')
    args = parser.parse_args()

    # Map model name to enum
    model_map = {
        'gpt4o-mini': ModelName.GPT4_MINI,
        'gpt4o': ModelName.GPT4
    }
    model_name = model_map[args.model]

    # Initialize the RAG system
    print(f"Initializing RAG system with {args.model} model...")
    rag_system = RAGSystem(args.directory, model_name)
    rag_system.initialize(reindex=args.reindex)

    # Print system information
    print("\nRAG System Information:")
    print(f"Configuration version: {rag_system.config.version}")
    print(f"Available datasources: {', '.join(rag_system.datasources)}")

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

            # Print the result
            print("\nResult:")
            print(f"Selected datasource: {result.get('datasource', 'None')}")
            print(f"Documents relevant: {'Yes' if result.get('documents_relevant') else 'No'}")
            print("\nResponse:")
            print(result.get('response', 'None'))

        except Exception as e:
            print(f"Error: {str(e)}")

    print("\nThank you for using the RAG system!")


if __name__ == "__main__":
    main()