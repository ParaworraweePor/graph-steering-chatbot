import os
from dotenv import load_dotenv

load_dotenv()

# Force the offline stubs by default so pytest never reaches Ollama / Neo4j.
os.environ.setdefault("EXTRACTOR", "stub")
os.environ.setdefault("GENERATOR", "echo")
os.environ.setdefault("GRAPH_BACKEND", "memory")
