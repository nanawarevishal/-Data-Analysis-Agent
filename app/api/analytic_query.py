import asyncio
from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
from app.schema.analytic_query_schema import QueryRequest, QueryResponse
from app.agents.analytic_agent import app


query_router = APIRouter(prefix="/query")


@query_router.post("/analyze", response_model=QueryResponse)
async def analyze_data(request: QueryRequest):
    """
    Receives a natural language question, invokes the agent graph,
    and returns the structured result.
    """
    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    inputs = {"question": request.question}

    try:
        result_state = await asyncio.to_thread(app.invoke, inputs)

        return QueryResponse(
            question=result_state.get("question", ""),
            sql_query=result_state.get("sql_query", ""),
            query_result=result_state.get("query_result", ""),
            final_answer=result_state.get("final_answer", ""),
            error=result_state.get("error"),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")
