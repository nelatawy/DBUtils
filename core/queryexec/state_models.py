from pydantic import model_validator, RootModel
from typing import Self, Dict, Any, List
        
class Row(RootModel[Dict[str, Any]]):
    pass

class TableState(RootModel[List[Row]]):
    @model_validator(mode="after")
    def enforce_uniform_schema(self) -> Self:
        if not self.root:
            return self  # Empty tables are valid

        def get_type(x : Any):
            return type(x)
        
        expected_attributes = list(self.root[0].root.keys())
        expected_types = list(map(get_type, self.root[0].root.values()))
        
        # Enforce that every row matches the baseline exactly
        for index, row in enumerate(self.root):
            current_attributes = list(row.root.keys())
            current_types = list(map(get_type, row.root.values()))
            if current_attributes != expected_attributes:
                raise ValueError(
                    "schema_mismatch",
                    f"Row index {index} violates table schema. "
                    f"Expected attributes {expected_attributes} with, but got {current_attributes}."
                )
            if current_types != expected_types:
                raise ValueError(
                    "schema_mismatch",
                    f"Row index {index} violates table schema. "
                    f"Expected types {expected_types} with, but got {current_types}."
                )
        return self

class DatabaseState(RootModel[Dict[str, TableState]]):
    pass


def main():
    test_case = ""
    with open("tests/table_state_test.json","r") as f:
        test_case = f.read()
    state = DatabaseState.model_validate_json(test_case)

if __name__ == '__main__':
    main()