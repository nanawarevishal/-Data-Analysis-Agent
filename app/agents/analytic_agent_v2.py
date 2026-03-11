import os
from typing import TypedDict, Optional, List, Annotated
from dotenv import load_dotenv
from operator import add

from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from app.config import get_settings

load_dotenv()
settings = get_settings()

DB_URI = settings.database_url
llm = ChatOpenAI(model="gpt-4o", temperature=0)
db = SQLDatabase.from_uri(DB_URI)


class AgentState(TypedDict):
    question: str
    chat_history: Annotated[List, add]
    table_names: List[str]
    sql_query: str
    query_result: str
    final_answer: str
    error: Optional[str]
    attempts: int


def select_tables_node(state: AgentState):
    question = state["question"]
    history = state.get("chat_history", [])

    all_tables = db.get_usable_table_names()

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a database expert. 
         Given a user question, a conversation history, and a list of available tables, 
         select ONLY the table names relevant to the final question.
         Return ONLY a comma-separated list of table names.
         
         Example:
         History: User asked about sales figures.
         Question: Which of those was highest?
         Relevant Tables: sales
         """,
            ),
            MessagesPlaceholder(variable_name="chat_history"),  # Inject History
            ("user", "Question: {question}\n\nAvailable Tables: {tables}"),
        ]
    )

    chain = prompt | llm
    response = chain.invoke(
        {
            "question": question,
            "tables": ", ".join(all_tables),
            "chat_history": history,  # Pass History
        }
    )

    selected_tables = [t.strip() for t in response.content.split(",")]
    valid_tables = [t for t in selected_tables if t in all_tables]

    if not valid_tables:
        valid_tables = all_tables

    return {"table_names": valid_tables}


def generate_sql_node(state: AgentState):
    """
    Generates SQL. Includes logic to fix errors if 'error' is present in state.
    """
    question = state["question"]
    history = state.get("chat_history", [])
    tables = state["table_names"]
    error = state.get("error")
    attempts = state.get("attempts", 0)

    table_info = db.get_table_info(tables)

    system_msg = """You are an expert PostgreSQL Data Analyst.
    Use the provided schema to write a valid PostgreSQL query.
    
    Schema:
    {schema}
    
    Important Rules:
    1. Only output the SQL query. No markdown formatting.
    2. For dates, use standard PostgreSQL format (YYYY-MM-DD).
    3. Be careful with JOIN conditions.
    4. If the user asks for "revenue", sum the 'total_amount'.
    """

    if error:
        system_msg += f"""
        
        CRITICAL: Your previous attempt failed with this error:
        {error}
        
        Please fix the SQL query and try again. Check for syntax errors or invalid column names.
        """

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_msg),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{question}"),
        ]
    )

    chain = prompt | llm

    response = chain.invoke(
        {"schema": table_info, "question": question, "chat_history": history}
    )

    sql_query = response.content.strip()
    if "```" in sql_query:
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

    return {"sql_query": sql_query, "attempts": attempts + 1, "error": None}


def execute_sql_node(state: AgentState):
    sql_query = state["sql_query"]
    try:
        result = db.run(sql_query)
        return {"query_result": result, "error": None}
    except Exception as e:
        print(f"--- SQL Error: {str(e)} ---")
        return {"error": str(e), "query_result": ""}


def generate_answer_node(state: AgentState):
    question = state["question"]
    sql = state["sql_query"]
    result = state["query_result"]
    history = state.get("chat_history", [])

    if state.get("error"):
        final_msg = f"I tried but failed to execute the query after multiple attempts. Error: {state['error']}"
        return {"final_answer": final_msg}

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant. Answer the user's question based on the SQL result.",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            (
                "user",
                "Question: {question}\nSQL Result: {result}\n\nProvide a concise natural language answer.",
            ),
        ]
    )

    chain = prompt | llm
    response = chain.invoke(
        {"question": question, "result": result, "chat_history": history}
    )

    return {"final_answer": response.content}


def should_retry(state: AgentState):
    """
    Conditional Edge: Decide if we retry SQL generation or proceed to answer.
    """
    if state.get("error") and state.get("attempts", 0) < 3:
        return "retry"
    return "answer"


workflow = StateGraph(AgentState)


workflow.add_node("select_tables", select_tables_node)
workflow.add_node("generate_sql", generate_sql_node)
workflow.add_node("execute_sql", execute_sql_node)
workflow.add_node("generate_answer", generate_answer_node)


workflow.set_entry_point("select_tables")

workflow.add_edge("select_tables", "generate_sql")
workflow.add_edge("generate_sql", "execute_sql")

workflow.add_conditional_edges(
    "execute_sql",
    should_retry,
    {"retry": "generate_sql", "answer": "generate_answer"},  # Loop back  # Proceed
)

workflow.add_edge("generate_answer", END)

app = workflow.compile()
