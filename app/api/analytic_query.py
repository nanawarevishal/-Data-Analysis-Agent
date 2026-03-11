import asyncio
from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
from app.schema.analytic_query_schema import QueryRequest, QueryResponse
from app.agents.analytic_agent_v2 import app


from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from typing import List, Optional
from app.agents.analytic_agent_v2 import app
from langchain_core.messages import HumanMessage, AIMessage
import asyncio


query_router = APIRouter(prefix="/query")
session_store = {}


@query_router.post("/analyze", response_model=QueryResponse)
async def analyze_data(request: QueryRequest):

    current_history = session_store.get(request.session_id, [])

    inputs = {"question": request.question, "chat_history": current_history}

    try:
        result_state = await asyncio.to_thread(app.invoke, inputs)

        updated_history = current_history.copy()
        updated_history.append(HumanMessage(content=request.question))
        updated_history.append(AIMessage(content=result_state["final_answer"]))

        session_store[request.session_id] = updated_history

        return QueryResponse(
            final_answer=result_state.get("final_answer"),
            sql_query=result_state.get("sql_query"),
            session_id=request.session_id,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@query_router.post("/reset")
async def reset_session(session_id: str = "default"):
    if session_id in session_store:
        del session_store[session_id]
    return {"status": "reset", "session_id": session_id}
