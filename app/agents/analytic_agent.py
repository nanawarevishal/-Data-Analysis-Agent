import os
from typing import TypedDict, Optional
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from app.config import get_settings


load_dotenv()


settings = get_settings()

DB_URI = settings.database_url

llm = ChatOpenAI(model="gpt-4o", temperature=0)


class AgentState(TypedDict):
    question: str
    sql_query: str
    query_result: str
    final_answer: str
    error: Optional[str]


def generate_sql_node(state: AgentState):
    question = state["question"]

    db = SQLDatabase.from_uri(DB_URI)

    table_info = db.get_table_info(["customers", "products", "orders"])

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert PostgreSQL Data Analyst.
         Use the provided schema to write a valid PostgreSQL query.
         
         Schema:
         {schema}
         
         Important Rules:
         1. Only output the SQL query. No markdown formatting.
         2. For dates, use standard PostgreSQL format (YYYY-MM-DD).
         3. Be careful with JOIN conditions.
         4. If the user asks for "revenue", sum the 'total_amount'.
         5. If the user asks about "sales", refer to the 'orders' table.
         """,
            ),
            ("user", "{question}"),
        ]
    )

    chain = prompt | llm
    response = chain.invoke({"schema": table_info, "question": question})

    sql_query = response.content.strip()

    # Clean markdown
    if "```" in sql_query:
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

    return {"sql_query": sql_query}


def execute_sql_node(state: AgentState):
    sql_query = state["sql_query"]
    db = SQLDatabase.from_uri(DB_URI)

    try:
        result = db.run(sql_query)
        return {"query_result": result, "error": None}
    except Exception as e:
        return {"error": str(e), "query_result": ""}


def generate_answer_node(state: AgentState):
    if state.get("error"):
        return {"final_answer": f"I encountered an error: {state['error']}"}

    question = state["question"]
    sql = state["sql_query"]
    result = state["query_result"]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant. Answer the user's question based on the SQL result.",
            ),
            (
                "user",
                "Question: {question}\nSQL Result: {result}\n\nProvide a concise natural language answer.",
            ),
        ]
    )

    chain = prompt | llm
    response = chain.invoke({"question": question, "result": result})
    return {"final_answer": response.content}


workflow = StateGraph(AgentState)
workflow.add_node("generate_sql", generate_sql_node)
workflow.add_node("execute_sql", execute_sql_node)
workflow.add_node("generate_answer", generate_answer_node)

workflow.set_entry_point("generate_sql")
workflow.add_edge("generate_sql", "execute_sql")
workflow.add_edge("execute_sql", "generate_answer")
workflow.add_edge("generate_answer", END)

app = workflow.compile()
