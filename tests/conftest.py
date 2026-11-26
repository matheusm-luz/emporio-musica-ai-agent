import pytest

from emporio_agent.data import StoreData, load_store_data
from emporio_agent.policies import PolicyManual


@pytest.fixture(scope="session")
def store() -> StoreData:
    return load_store_data()


@pytest.fixture(scope="session")
def manual() -> PolicyManual:
    return PolicyManual.load()
