import os

import pytest


def pytest_configure(config):
    # CredentialsStore fails closed without a key; set before backend app import.
    os.environ.setdefault("CREDENTIALS_ENCRYPTION_KEY", "test-credentials-key")
    config.addinivalue_line("markers", "llm: live LLM eval (requires LLM_EVAL=1 and configured provider)")
