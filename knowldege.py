import os
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb
from dotenv import load_dotenv
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder

load_dotenv()

def create_user_kb(user_id: str, pdf_path: str):
    vector_db = LanceDb(
    table_name=f"user_{user_id}_docs",
    uri="./lancedb_store",
    embedder=SentenceTransformerEmbedder(
        id="all-MiniLM-L6-v2"

        )
)
    kb = Knowledge(
        vector_db=vector_db,
    )
     

    kb.insert(path=pdf_path)


    
    return kb

if __name__ == "__main__":
    kb = create_user_kb("demo_user", "company_new.pdf")

    print("KB created successfully")

    results = kb.search("What are the work hours?")
    print(results)

    