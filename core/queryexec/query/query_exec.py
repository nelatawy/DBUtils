from core.queryexec.query.query_parser import QueryParser
from core.queryexec.conditions.condition_eval import ConditionEvaluater
from core.queryexec.conditions.condition_parser import ConditionParser
from core.queryexec.state_models import DatabaseState, TableState
from core.queryexec.ast_models import *

# maps from DatabaseState to python matrices
# first row is attribute names and the rest are values

class MappedTable:
    def __init__(self, table_name : str, table_rows : TableState):
        self.name = table_name
        self.attribs = list(table_rows.root[0].root.keys()) if table_rows else None
        self.rows = []

        if not table_rows:
            return
        for i in range(1, len(table_rows.root)):
            row = table_rows.root[i]
            self.rows.append(list(row.root.values()))

    def set_attributes(self, attribs : list[str]):
        self.attribs = attribs[:]

    def add_row(self, row : list[any]):
        self.rows.append(row)


class TableUtils:

    @staticmethod
    def project_table(table : MappedTable, proj_attr : list[str]) -> MappedTable:
        selected_indices = set()
        proj_attr = set(proj_attr)

        res_table = MappedTable("", None)
        res_table.set_attributes(list(filter(lambda x : x in proj_attr, table.attribs)))

        for i in range(len(table[0])):
            if table[0][i] in proj_attr:
                selected_indices.add(i)
        
        for i in range(1, len(table)):
            row = table[i]
            mapped_row = []
            for j in range(len(row)):
                if j not in selected_indices:
                    continue
                mapped_row.append(row[j])
            res_table.add_row(mapped_row)
        return res_table
            
    @staticmethod
    def select_from_table(table : MappedTable, cond_tree) -> MappedTable:
        res_table = MappedTable("", None)
        res_table.set_attributes(table.attribs)

        for row in table.rows:
            values = dict()
            for j in range(len(res_table.attribs)):
                values[res_table.attribs[j]] = row[j]
            
            valid_row = ConditionEvaluater.evaluate(cond_tree, values)
            if valid_row:
                res_table.add_row(row[:])
        
        return res_table

    @staticmethod
    def join_tables(first : MappedTable, second : MappedTable, cond_tree) -> MappedTable:
        res_table = MappedTable("",None)
        res_table.set_attributes(first.attribs + second.attribs)
        has_overlapping_attribs = (len(set(first.attribs).intersection(second.attribs)) != 0)
        
        natural_join = (isinstance(cond_tree, AtomicNode))
        if natural_join:
            join_attrib = cond_tree.val
            join_attrib_indices = first.attribs.index(join_attrib), second.attribs.index(join_attrib)
            if not (join_attrib_indices[0] and join_attrib_indices[1]):
                raise ValueError("Can't perform natural JOIN if tables don't have the JOIN attribute")
            
            for row1 in first.rows:
                for row2 in second.rows:
                    if row1[join_attrib_indices[0]] == row2[join_attrib_indices[1]]:
                        res_table.add_row(row1 + row2)
        else:
            if has_overlapping_attribs and first.name == second.name:
                raise ValueError("Can't perform a theta join on 2 anonymous tables with overlapping attrib names")
            
            # by the time we pass we are sure that either there's no overalpping attributes or one of them is named
            for row1 in first.rows:
                values = dict()
                for j in range(len(row1)):
                    
                    if not has_overlapping_attribs or (not first.name or not first.name.strip()):
                        # if this is the anonymous table we should set the value by column name directly
                        values[first.attribs[j]] = row1[j]

                    if first.name and first.name.strip():
                        # to support both table.attrib and just attrib
                        values[f"{first.name}.{first.attribs[j]}"] = row1[j]

                for row2 in second.rows:
                    for j in range(len(row2)):

                        if not has_overlapping_attribs or (not second.name or not second.name.strip()):
                            # if this is the anonymous table we should set the value by column name directly
                            values[second.attribs[j]] = row2[j]

                        if second.name and second.name.strip():
                            # to support both table.attrib and just attrib
                            values[f"{second.name}.{second.attribs[j]}"] = row2[j]

                    valid_row = ConditionEvaluater.evaluate(cond_tree, values)
                    if valid_row:
                        res_table.add_row(row1 + row2)

        return res_table            


class QueryExecuter:
    def __init__(self):
        self.tables = {}

    def evaluate(self, node : BinaryNode | UnaryNode | AtomicNode):
        if isinstance(node, AtomicNode):
            return self.tables[node.val]

        if node.operator == "SELECT":
            table = self.evaluate(node.first)
            return TableUtils.select_from_table(table, node.condition)
        
        elif node.operator == "PROJECT":
            table = self.evaluate(node.first)
            return TableUtils.project_table(table, node.condition)
        
        elif node.operator == "JOIN":
            first = self.evaluate(node.first)
            second = self.evaluate(node.second)
            return TableUtils.join_tables(first, second, node.condition)
        
        elif node.operator in {"UNION", "INTERSECT", "DIFFERENCE", "AGGREGATE"}:
            raise NotImplementedError(
                f"{node.operator} is not implemented in TableUtils"
            )

        raise ValueError(f"Unsupported query operator: {node.operator}")


def main():
    table = [["emp_id", "name", "age"],
             [500, "Jogn Doe", 35],
             [457, "Jane Smith", 24]]
    print(TableUtils.project_table(table, ["emp_id", "name"]))
if __name__ == '__main__':
    main()
