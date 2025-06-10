# test_rag_debug.py
"""
Script de teste para debugar o erro no sistema RAG
Execute este script para identificar onde está ocorrendo o erro
"""
import os
import sys
from dotenv import load_dotenv

# Adiciona o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from source.constantes.models import ModelName
from source.rag.system import RAGSystem
from source.rag.logging import RAGLogger

load_dotenv()


def test_rag_system():
    print("=== TESTE DE DEBUG DO SISTEMA RAG ===")

    # 1. Teste básico de inicialização
    print("\n1. Testando inicialização do sistema...")

    try:
        thread_config = {"configurable": {"thread_id": "test_debug_001"}}

        # Cria logger
        logger = RAGLogger(
            thread_id="test_debug_001",
            persona_id="test_user",
            log_dir="source/tests/integratio_test/rag_logs_debug"
        )

        # Cria sistema RAG
        rag_system = RAGSystem(
            base_path="./RAG Cartões",
            thread_id=thread_config,
            model_name=ModelName.GPT4_MINI,
            logger=logger,
            persona_id="test_user"
        )

        print("   ✓ RAGSystem criado com sucesso")

    except Exception as e:
        print(f"   ✗ Erro ao criar RAGSystem: {type(e).__name__}: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return

    # 2. Teste de inicialização
    print("\n2. Testando inicialização do workflow...")

    try:
        rag_system.initialize(reindex=False)
        print("   ✓ Sistema inicializado com sucesso")
    except Exception as e:
        print(f"   ✗ Erro ao inicializar sistema: {type(e).__name__}: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return

    # 3. Teste de query simples
    print("\n3. Testando query simples...")

    try:
        test_query = "Como posso aumentar o limite do meu cartão?"
        print(f"   Query: {test_query}")

        result = rag_system.query(test_query)

        print("   ✓ Query executada com sucesso")
        print(f"   Datasource selecionado: {result.get('datasource')}")
        print(f"   Documentos relevantes: {result.get('documents_relevant')}")
        print(f"   Resposta: {result.get('response', '')[:100]}...")

    except Exception as e:
        print(f"   ✗ Erro ao executar query: {type(e).__name__}: {str(e)}")
        import traceback
        print(traceback.format_exc())

        # Tenta gerar logs mesmo com erro
        try:
            zip_path = rag_system.generate_logs_zip()
            print(f"\n   Logs de debug salvos em: {zip_path}")
        except:
            pass

        return

    # 4. Gera logs finais
    print("\n4. Gerando logs...")

    try:
        zip_path = rag_system.generate_logs_zip()
        print(f"   ✓ Logs salvos em: {zip_path}")
    except Exception as e:
        print(f"   ✗ Erro ao gerar logs: {type(e).__name__}: {str(e)}")

    # 5. Fecha o sistema
    try:
        rag_system.close()
        print("\n✓ Teste concluído")
    except:
        pass


if __name__ == "__main__":
    # Verifica se a API key está configurada
    if not os.getenv("OPENAI_API_KEY"):
        print("ERRO: OPENAI_API_KEY não configurada")
        sys.exit(1)

    # Executa o teste
    test_rag_system()