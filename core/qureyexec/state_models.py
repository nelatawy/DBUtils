from pydantic import BaseModel, Field, model_validator, RootModel
from typing import Self, Dict, Any, List
        
class Row(RootModel[Dict[str, Any]]):
    pass


class TableState(RootModel[List[Row]]):
    @model_validator(mode="after")
    def enforce_uniform_schema(self) -> "TableState":
        if not self.root:
            return self  # Empty tables are valid
            
        expected_attributes = set(self.root[0].root.keys())
        
        # Enforce that every row matches the baseline exactly
        for index, row in enumerate(self.root):
            current_attributes = set(row.root.keys())
            if current_attributes != expected_attributes:
                raise ValueError(
                    "schema_mismatch",
                    f"Row index {index} violates table schema. "
                    f"Expected attributes {expected_attributes}, but got {current_attributes}."
                )
        return self

class DatabaseState(RootModel[Dict[str, TableState]]):
    pass