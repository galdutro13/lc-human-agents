import os
from source.rag.config import ConfigurationManager, YAMLConfigurationStrategy
from source.rag.document import FileSystemDocumentLoader, StandardDocumentProcessor


def setup_rag_components(base_path: str):
    """
    Example function showing how to set up the RAG components.

    Args:
        base_path: Base path where the RAG configuration and documents are located
    """
    # 1. Load configuration
    config_path = os.path.join(base_path, "config.yaml")
    config_manager = ConfigurationManager(YAMLConfigurationStrategy())
    config_manager.load(config_path)
    config = config_manager.config

    print(f"Configuration loaded: version {config.version}")
    print(f"Number of datasources: {len(config.datasources)}")

    # 2. Load documents
    document_loader = FileSystemDocumentLoader()
    documents = document_loader.load_documents(config, base_path)

    # 3. Process documents
    document_processor = StandardDocumentProcessor()
    processed_documents = document_processor.process_documents(documents, config)

    # Summarize results
    total_docs_before = sum(len(docs) for docs in documents.values())
    total_docs_after = sum(len(docs) for docs in processed_documents.values())

    print(f"Documents loaded and processed:")
    print(f"  - Original documents: {total_docs_before}")
    print(f"  - Processed chunks: {total_docs_after}")

    # Return components for further use
    return {
        "config": config,
        "documents": documents,
        "processed_documents": processed_documents
    }


if __name__ == "__main__":
    # Example usage
    rag_components = setup_rag_components("./RAG Cartões")

    # Access the components
    config = rag_components["config"]
    documents = rag_components["documents"]
    processed_documents = rag_components["processed_documents"]

    # Print some information about the loaded data
    print("\nDatasource details:")
    for datasource in config.datasources:
        doc_count = len(documents.get(datasource.name, []))
        chunk_count = len(processed_documents.get(datasource.name, []))
        print(f"  - {datasource.display_name}: {doc_count} docs, {chunk_count} chunks")