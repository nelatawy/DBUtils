from query_parser import QueryParser
from state_models import DatabaseState, TableState

# maps from DatabaseState to python matrices
# first row is attribute names and the rest are values
class DatabaseMapper:
    
    @staticmethod
    def map_table(table_state : TableState) -> list[list]:
        mapped = []
        mapped.append(list(table_state.root[0].root.keys()))

        for i in range(1, len(table_state.root)):
            row = table_state.root[i]
            mapped.append(list(row.root.values()))
        return mapped

    @staticmethod
    def project_table(table : list[list], proj_attr : list[str]) -> list[list]:
        selected_indices = set()

        for i in range(len(table[0])):
            if table[0][i] in proj_attr:
                selected_indices.add(i)
        mapped = []
        for i in range(len(table)):
            row = table[i]
            mapped_row = []
            for j in range(len(row)):
                if j not in selected_indices:
                    continue
                mapped_row.append(row[j])
            mapped.append(mapped_row)
        return mapped
            
    # @staticmethods
    # def select_from_table(table : list[list], )

class QueryExecuter:
    def __init__(self):
        self.tables = {}

    def __eval_select(node):
        pass

    def __eval_project(node):
        pass

    def __eval_join(node):
        pass

    def __eval_union(node):
        pass

    def __eval_intersect(node):
        pass

    def __eval_difference(node):
        pass

    def __eval_aggregate(node):
        pass
