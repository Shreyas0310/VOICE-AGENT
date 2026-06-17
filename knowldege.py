import os
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.lancedb import LanceDb
from dotenv import load_dotenv

load_dotenv()

def create_user_kb(user_id: str, pdf_path: str):
    vector_db = LanceDb(
        table_name=f"user_{user_id}_docs",
        uri="./lancedb_store",

    )
    
    kb = Knowledge(
        vector_db=vector_db,
    )
    
    # PDF insert karo
    kb.insert(path=pdf_path)
    
    return kb

if __name__ == "__main__":
    kb = create_user_kb("user123", "test.pdf")
    print("✅ Knowledge base ready!")