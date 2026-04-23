"""org_context data source component."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, DataSource
from component_library.registry import register


class Person(BaseModel):
    name: str
    role: str
    email: str
    communication_preference: str = "email"
    relationship: str = "colleague"


@register("org_context")
class OrgContext(DataSource):
    config_schema = {
        "people": {"type": "list", "required": False, "description": "People, roles, emails, and communication preferences in the org map.", "default": []},
        "escalation_chain": {"type": "list", "required": False, "description": "Ordered escalation contacts or roles.", "default": []},
        "firm_info": {"type": "dict", "required": False, "description": "Organization-specific metadata and operating context.", "default": {}},
    }
    component_id = "org_context"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._people = [Person(**person) if not isinstance(person, Person) else person for person in config.get("people", [])]
        self._escalation_chain = config.get("escalation_chain", [])
        self._firm_info = config.get("firm_info", {})

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/data/test_org_context.py"]

    async def query(self, query: str, **kwargs: Any) -> Any:
        lower = query.lower()
        if "supervisor" in lower:
            return self.get_supervisor()
        if "escalation" in lower:
            return self.get_escalation_chain()
        return self.get_person(query)

    def get_supervisor(self) -> Person | None:
        for person in self._people:
            if person.relationship == "supervisor":
                return person
        if self._escalation_chain:
            return self.get_person(self._escalation_chain[0])
        return None

    def get_escalation_chain(self) -> list[Person]:
        result: list[Person] = []
        for name in self._escalation_chain:
            person = self.get_person(name)
            if person is not None:
                result.append(person)
        return result

    def get_person(self, name: str) -> Person | None:
        lower = name.lower()
        for person in self._people:
            if person.name.lower() == lower or lower in person.name.lower():
                return person
        return None

    def get_firm_info(self) -> dict[str, Any]:
        return dict(self._firm_info)
