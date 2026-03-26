from __future__ import annotations

from mentor_index.adapters.base import FacultyAdapter
from mentor_index.adapters.zju_control import ZjuControlAdapter
from mentor_index.adapters.zju_person import SCHOOL_CONFIGS, ZjuPersonSearchAdapter


def get_adapter(name: str) -> FacultyAdapter:
    adapters = {"zju_control": ZjuControlAdapter()}
    adapters.update({adapter_name: ZjuPersonSearchAdapter(config) for adapter_name, config in SCHOOL_CONFIGS.items()})
    if name not in adapters:
        raise KeyError(f"Unknown adapter: {name}")
    return adapters[name]
