# app/services/sales_agent/serializers.py
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import (
    HttpUrl,
    EmailStr,
)

from typing import Any, Tuple


class JsonOnlySerializer(JsonPlusSerializer):
    def _default(self, o: Any) -> Any:
        if isinstance(o, HttpUrl):
            return str(o)
        if isinstance(o, EmailStr):
            return str(o)
        try:
            return super()._default(o)
        except TypeError:  # Catch broader TypeError from super if it can't handle
            raise TypeError(
                f"Object of type {o.__class__.__name__} is not JSON serializable by JsonOnlySerializer's fallback"
            )

    def dumps_typed(self, obj: Any) -> Tuple[str, bytes]:
        return "json", self.dumps(obj)
