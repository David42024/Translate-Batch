import os
import logging
logging.basicConfig(level=logging.INFO)
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["GEMINI_API_KEY"] = "fake"

from agent_service import _translate_agent_chunk

try:
    _translate_agent_chunk("Hello world")
    print("Success")
except Exception as e:
    print(f"Error: {e}")
