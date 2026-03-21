from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]


def _load_module(rel_path: str, module_name: str):
    module_path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_langfuse_handler_returns_none_when_disabled_or_keys_missing(monkeypatch):
    mod = _load_module("hr_agent/configs/config.py", "config_mod_disabled")

    monkeypatch.setattr(mod, "_langfuse_handler", None)
    monkeypatch.setattr(mod.settings, "langfuse_enabled", False)
    assert mod.get_langfuse_handler() is None

    monkeypatch.setattr(mod.settings, "langfuse_enabled", True)
    monkeypatch.setattr(mod.settings, "langfuse_public_key", "")
    monkeypatch.setattr(mod.settings, "langfuse_secret_key", "")
    assert mod.get_langfuse_handler() is None


def test_langfuse_handler_sets_env_and_caches_instance(monkeypatch):
    mod = _load_module("hr_agent/configs/config.py", "config_mod_handler")

    class FakeCallbackHandler:
        pass

    langchain_module = ModuleType("langfuse.langchain")
    langchain_module.CallbackHandler = FakeCallbackHandler
    langfuse_module = ModuleType("langfuse")
    langfuse_module.langchain = langchain_module

    monkeypatch.setitem(sys.modules, "langfuse", langfuse_module)
    monkeypatch.setitem(sys.modules, "langfuse.langchain", langchain_module)
    monkeypatch.setattr(mod, "_langfuse_handler", None)
    monkeypatch.setattr(mod.settings, "langfuse_enabled", True)
    monkeypatch.setattr(mod.settings, "langfuse_public_key", "public-key")
    monkeypatch.setattr(mod.settings, "langfuse_secret_key", "secret-key")
    monkeypatch.setattr(mod.settings, "langfuse_host", "https://langfuse.example")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    first = mod.get_langfuse_handler()
    second = mod.get_langfuse_handler()

    assert isinstance(first, FakeCallbackHandler)
    assert first is second
    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "public-key"
    assert os.environ["LANGFUSE_SECRET_KEY"] == "secret-key"
    assert os.environ["LANGFUSE_HOST"] == "https://langfuse.example"


def test_langfuse_client_returns_none_when_disabled_or_keys_missing(monkeypatch):
    mod = _load_module("hr_agent/configs/config.py", "config_mod_client_none")

    monkeypatch.setattr(mod, "_langfuse_client", None)
    monkeypatch.setattr(mod.settings, "langfuse_enabled", False)
    assert mod.get_langfuse_client() is None

    monkeypatch.setattr(mod.settings, "langfuse_enabled", True)
    monkeypatch.setattr(mod.settings, "langfuse_public_key", "")
    monkeypatch.setattr(mod.settings, "langfuse_secret_key", "")
    assert mod.get_langfuse_client() is None


def test_langfuse_client_sets_env_and_caches_instance(monkeypatch):
    mod = _load_module("hr_agent/configs/config.py", "config_mod_client")

    class FakeLangfuse:
        pass

    langfuse_module = ModuleType("langfuse")
    langfuse_module.Langfuse = FakeLangfuse

    monkeypatch.setitem(sys.modules, "langfuse", langfuse_module)
    monkeypatch.setattr(mod, "_langfuse_client", None)
    monkeypatch.setattr(mod.settings, "langfuse_enabled", True)
    monkeypatch.setattr(mod.settings, "langfuse_public_key", "public-key")
    monkeypatch.setattr(mod.settings, "langfuse_secret_key", "secret-key")
    monkeypatch.setattr(mod.settings, "langfuse_host", "https://langfuse.example")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)

    first = mod.get_langfuse_client()
    second = mod.get_langfuse_client()

    assert isinstance(first, FakeLangfuse)
    assert first is second
    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "public-key"
    assert os.environ["LANGFUSE_SECRET_KEY"] == "secret-key"
    assert os.environ["LANGFUSE_HOST"] == "https://langfuse.example"
