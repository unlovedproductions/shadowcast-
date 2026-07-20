import pytest

def pytest_configure(config):
    config.addinivalue_line("markers", "llm: live LLM eval (requires LLM_EVAL=1 and configured provider)")
