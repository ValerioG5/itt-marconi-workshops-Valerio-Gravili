import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "req(*args): collega il test al requisito identificato da args (es. REQ-REG-B01)",
    )
