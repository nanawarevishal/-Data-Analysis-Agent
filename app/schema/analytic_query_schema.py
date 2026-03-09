# 1. Define Request/Response Models (Pydantic)
from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    sql_query: str
    query_result: str
    final_answer: str
    error: str | None = None
