# 1. Define Request/Response Models (Pydantic)
from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    session_id: str = "default"  # Default session for easy testing


class QueryResponse(BaseModel):
    final_answer: str
    sql_query: str
    session_id: str
