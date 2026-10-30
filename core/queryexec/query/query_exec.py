from core.queryexec.query.query_parser import QueryParser
from core.queryexec.conditions.condition_eval import ConditionEvaluater
from core.queryexec.conditions.condition_parser import ConditionParser
from core.queryexec.state_models import DatabaseState, TableState
from core.queryexec.ast_models import *



class MappedTable:
    def __init__(self, table_name : str, table_rows : TableState):
        self.name = table_name
        self.attribs = list(table_rows.root[0].root.keys()) if table_rows else None
        self.rows = []

        if not table_rows:
            return
        for i in range(len(table_rows.root)):
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

        seen_rows = set()
        for i, attribute in enumerate(table.attribs):
            if attribute in proj_attr:
                selected_indices.add(i)
        
        for row in table.rows:
            new_row = []
            for index, value in enumerate(row):
                if index in selected_indices:
                    new_row.append(value)
            
            row_tuple = tuple(new_row)
            if row_tuple not in seen_rows:
                seen_rows.add(row_tuple)
                res_table.add_row(new_row)

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
            if join_attrib not in first.attribs or join_attrib not in second.attribs:
                raise ValueError("Can't perform natural JOIN if tables don't have the JOIN attribute")
            join_attrib_indices = first.attribs.index(join_attrib), second.attribs.index(join_attrib)
            
            for row1 in first.rows:
                for row2 in second.rows:
                    if row1[join_attrib_indices[0]] == row2[join_attrib_indices[1]]:
                        res_table.add_row(row1 + row2)
        else:
            if has_overlapping_attribs and first.name == second.name:
                raise ValueError("Can't perform a theta join on 2 anonymous tables with overlapping attrib names")
            
            # At this point, columns do not overlap or table names disambiguate them.
            for row1 in first.rows:
                values = dict()
                for j in range(len(row1)):
                    
                    if not has_overlapping_attribs or (not first.name or not first.name.strip()):
                        # For anonymous tables, use column names directly.
                        values[first.attribs[j]] = row1[j]

                    if first.name and first.name.strip():
                        # to support both table.attrib and just attrib
                        values[f"{first.name}.{first.attribs[j]}"] = row1[j]

                for row2 in second.rows:
                    for j in range(len(row2)):

                        if not has_overlapping_attribs or (not second.name or not second.name.strip()):
                            # For anonymous tables, use column names directly.
                            values[second.attribs[j]] = row2[j]

                        if second.name and second.name.strip():
                            # to support both table.attrib and just attrib
                            values[f"{second.name}.{second.attribs[j]}"] = row2[j]

                    valid_row = ConditionEvaluater.evaluate(cond_tree, values)
                    if valid_row:
                        res_table.add_row(row1 + row2)

        return res_table            

    @staticmethod
    def union_tables(first : MappedTable, second : MappedTable) -> MappedTable:
        if first.attribs != second.attribs:
            raise ValueError("Tables must be UNION compatible check the arity of both tables and make sure the attributes match")

        res_table = MappedTable("",None)
        res_table.set_attributes(first.attribs)
        for row in first.rows:
            res_table.add_row(row)
        for row in second.rows:
            res_table.add_row(row)
        return res_table

    @staticmethod
    def intersect_tables(first : MappedTable, second : MappedTable) -> MappedTable:
        if first.attribs != second.attribs:
            raise ValueError("Tables must be INTERSECT compatible check the arity of both tables and make sure the attributes match")
        
        res_table = MappedTable("",None)
        res_table.set_attributes(first.attribs)

        first_rows = set([tuple(row) for row in first.rows])
        second_rows =set([tuple(row) for row in second.rows])

        final_rows = [list(row) for row in first_rows.intersection(second_rows)]
        # Add the resulting rows.
        for row in final_rows:
            res_table.add_row(row)
        
        return res_table

    @staticmethod
    def difference_table(first : MappedTable, second : MappedTable) -> MappedTable:
        if first.attribs != second.attribs:
            raise ValueError("Tables must be DIFFERENCE compatible check the arity of both tables and make sure the attributes match")
        
        res_table = MappedTable("",None)
        res_table.set_attributes(first.attribs)

        first_rows = set([tuple(row) for row in first.rows])
        second_rows =set([tuple(row) for row in second.rows])

        final_rows = [list(row) for row in first_rows.difference(second_rows)]
        # Add the resulting rows.
        for row in final_rows:
            res_table.add_row(row)
        
        return res_table


    def __get_aggr_func(aggr : str):
        return aggr.split("(", 1)[0].strip().upper()
    
    def __get_aggr_attr(aggr : str):
        if "(" not in aggr or not aggr.endswith(")"):
            raise ValueError(f"Invalid aggregation expression: {aggr}")
        return aggr.split("(", 1)[1][:-1].strip()

    @staticmethod
    def aggregate_table(table : MappedTable, aggregations : list[str]) -> MappedTable:
        # Expected syntax: [MAX(salary), MIN(salary), AVG(salary)].
        res_table = MappedTable("", None)
        attrib_set = set(table.attribs)

        for aggr in aggregations:
            attr = TableUtils.__get_aggr_attr(aggr)
            if not attr or attr not in attrib_set:
                raise ValueError("can't aggregate a non existing attribute")
            
        res_table.set_attributes(aggregations)
        aggr_row = []

        for aggr in aggregations:
            aggr_attr = TableUtils.__get_aggr_attr(aggr)
            aggr_func = TableUtils.__get_aggr_func(aggr)

            attr_idx = table.attribs.index(aggr_attr)
            aggr_res = None if aggr_func != "AVG" else 0
            

            for row in table.rows:
                val = row[attr_idx]
                if aggr_func == "AVG":
                    aggr_res += val

                elif aggr_func == "MAX":
                    if not aggr_res:
                        aggr_res = val
                    else:
                        aggr_res = max(aggr_res, val)

                elif aggr_func == "MIN":
                    if not aggr_res:
                        aggr_res = val
                    else:
                        aggr_res = min(aggr_res, val)

                else:
                    raise ValueError(f"Aggregation of type {aggr_func} is not allowed")

            if aggr_func == "AVG" and len(table.rows):
                aggr_res /= len(table.rows)
            aggr_row.append(aggr_res)

        res_table.add_row(aggr_row)
        return res_table

class QueryExecuter:
    def __init__(self):
        self.tables = {}

    def addTable(self, table: MappedTable):
        if not table.name or not table.name.strip():
            raise ValueError("A table must have a non-empty name")
        self.tables[table.name] = table

    def evaluate(self, node : BinaryNode | UnaryNode | AtomicNode):
        if isinstance(node, AtomicNode):
            return self.tables[node.val]
        
        first = self.evaluate(node.first)
        second = self.evaluate(node.second) if isinstance(node, BinaryNode) else None

        if node.operator == "SELECT":
            return TableUtils.select_from_table(first, node.extra)
        
        elif node.operator == "PROJECT":
            return TableUtils.project_table(first, node.extra)
    
        elif node.operator == "JOIN":
            return TableUtils.join_tables(first, second, node.extra)
        
        elif node.operator == "UNION":
            return TableUtils.union_tables(first, second)
        
        elif node.operator == "INTERSECT":
            return TableUtils.intersect_tables(first, second)

        elif node.operator == "DIFFERENCE":
            return TableUtils.difference_table(first, second)
        
        elif node.operator == "AGGREGATE":
            return TableUtils.aggregate_table(first, node.extra)

        raise ValueError(f"Unsupported query operator: {node.operator}")


def main():
    def make_table(name, attributes, rows):
        table = MappedTable(name, None)
        table.set_attributes(attributes)
        for row in rows:
            table.add_row(row)
        return table

    def check_result(test_name, result, expected_attributes, expected_rows):
        assert result.attribs == expected_attributes, (
            f"{test_name}: expected columns {expected_attributes}, got {result.attribs}"
        )
        actual = {tuple(row) for row in result.rows}
        expected = {tuple(row) for row in expected_rows}
        assert actual == expected, (
            f"{test_name}: expected rows {expected}, got {actual}"
        )
        print(f"PASS: {test_name} ({len(result.rows)} rows)")

    def check_query(test_name, query, expected_attributes, expected_rows):
        result = evaluator.evaluate(QueryParser.parse(query))
        check_result(test_name, result, expected_attributes, expected_rows)

    employees = make_table(
        "Employees",
        ["employee_id", "name", "dept_id", "salary"],
        [
            [101, "Ava Chen", 10, 128000],
            [102, "Noah Patel", 20, 96000],
            [103, "Mia Brooks", 10, 113000],
            [104, "Liam Rivera", 30, 87000],
            [105, "Zoe Kim", 20, 104000],
            [106, "Ethan Shah", 30, 99000],
            [107, "Ivy Nguyen", 10, 142000],
            [108, "Leo Martin", 20, 76000],
        ],
    )
    departments = make_table(
        "Departments",
        ["dept_id", "dept_name", "city"],
        [
            [10, "Engineering", "Seattle"],
            [20, "Research", "Boston"],
            [30, "Operations", "Austin"],
        ],
    )
    archived_employees = make_table(
        "ArchivedEmployees",
        ["employee_id", "name", "dept_id", "salary"],
        [
            [101, "Ava Chen", 10, 128000],
            [104, "Liam Rivera", 30, 87000],
            [108, "Leo Martin", 20, 76000],
            [109, "Grace Park", 10, 91000],
        ],
    )

    evaluator = QueryExecuter()
    for table in (employees, departments, archived_employees):
        evaluator.addTable(table)

    # Test each implemented relational-algebra operation.
    projected = evaluator.evaluate(
        QueryParser.parse("PROJECT{name,salary} Employees")
    )
    check_result(
        "PROJECT",
        projected,
        ["name", "salary"],
        [[row[1], row[3]] for row in employees.rows],
    )

    selected = evaluator.evaluate(
        UnaryNode("SELECT", AtomicNode("Employees"), ConditionParser.parse("salary >= 100000"))
    )
    check_result(
        "SELECT",
        selected,
        employees.attribs,
        [row for row in employees.rows if row[3] >= 100000],
    )

    joined = evaluator.evaluate(
        BinaryNode("JOIN", AtomicNode("Employees"), AtomicNode("Departments"),
                   ConditionParser.parse("Employees.dept_id == Departments.dept_id"))
    )
    check_result(
        "JOIN",
        joined,
        employees.attribs + departments.attribs,
        [employee + department for employee in employees.rows
         for department in departments.rows if employee[2] == department[0]],
    )

    unioned = evaluator.evaluate(
        BinaryNode("UNION", AtomicNode("Employees"), AtomicNode("ArchivedEmployees"))
    )
    check_result(
        "UNION",
        unioned,
        employees.attribs,
        employees.rows + archived_employees.rows,
    )

    intersected = evaluator.evaluate(
        BinaryNode("INTERSECT", AtomicNode("Employees"), AtomicNode("ArchivedEmployees"))
    )
    check_result(
        "INTERSECT",
        intersected,
        employees.attribs,
        [row for row in employees.rows if row in archived_employees.rows],
    )

    differenced = evaluator.evaluate(
        BinaryNode("DIFFERENCE", AtomicNode("Employees"), AtomicNode("ArchivedEmployees"))
    )
    check_result(
        "DIFFERENCE",
        differenced,
        employees.attribs,
        [row for row in employees.rows if row not in archived_employees.rows],
    )

    # Parse aggregations directly from AGGREGATE{FUNC(attribute),...}.
    aggregated = evaluator.evaluate(
        QueryParser.parse(
            "AGGREGATE{MAX(salary),MIN(salary),AVG(salary)} Employees"
        )
    )
    salaries = [row[3] for row in employees.rows]
    check_result(
        "AGGREGATE MAX/MIN/AVG",
        aggregated,
        ["MAX(salary)", "MIN(salary)", "AVG(salary)"],
        [[max(salaries), min(salaries), sum(salaries) / len(salaries)]],
    )

    # Verify recursive evaluation with JOIN -> SELECT -> PROJECT.
    multi_result = evaluator.evaluate(
        UnaryNode(
            "PROJECT",
            UnaryNode(
                "SELECT",
                BinaryNode(
                    "JOIN",
                    AtomicNode("Employees"),
                    AtomicNode("Departments"),
                    ConditionParser.parse("Employees.dept_id == Departments.dept_id"),
                ),
                ConditionParser.parse("salary >= 100000"),
            ),
            ["name", "dept_name"],
        )
    )
    check_result(
        "JOIN -> SELECT -> PROJECT",
        multi_result,
        ["name", "dept_name"],
        [[employee[1], department[1]]
         for employee in employees.rows
         for department in departments.rows
         if employee[2] == department[0] and employee[3] >= 100000],
    )

    # Repeat the operation tests from query strings to cover parsing and evaluation,
    # rather than building AST nodes by hand.
    check_query(
        "QUERY PROJECT",
        "PROJECT{name,salary} Employees",
        ["name", "salary"],
        [[row[1], row[3]] for row in employees.rows],
    )
    check_query(
        "QUERY SELECT",
        "SELECT[salary >= 100000] Employees",
        employees.attribs,
        [row for row in employees.rows if row[3] >= 100000],
    )
    check_query(
        "QUERY JOIN",
        "Employees JOIN[Employees.dept_id == Departments.dept_id] Departments",
        employees.attribs + departments.attribs,
        [employee + department for employee in employees.rows
         for department in departments.rows if employee[2] == department[0]],
    )
    check_query(
        "QUERY UNION",
        "Employees UNION ArchivedEmployees",
        employees.attribs,
        employees.rows + archived_employees.rows,
    )
    check_query(
        "QUERY INTERSECT",
        "Employees INTERSECT ArchivedEmployees",
        employees.attribs,
        [row for row in employees.rows if row in archived_employees.rows],
    )
    check_query(
        "QUERY DIFFERENCE",
        "Employees DIFFERENCE ArchivedEmployees",
        employees.attribs,
        [row for row in employees.rows if row not in archived_employees.rows],
    )
    check_query(
        "QUERY AGGREGATE",
        "AGGREGATE{MAX(salary),MIN(salary),AVG(salary)} Employees",
        ["MAX(salary)", "MIN(salary)", "AVG(salary)"],
        [[max(salaries), min(salaries), sum(salaries) / len(salaries)]],
    )
    check_query(
        "QUERY JOIN -> SELECT -> PROJECT",
        "PROJECT{name,dept_name} SELECT[salary >= 100000] "
        "(Employees JOIN[Employees.dept_id == Departments.dept_id] Departments)",
        ["name", "dept_name"],
        [[employee[1], department[1]]
         for employee in employees.rows
         for department in departments.rows
         if employee[2] == department[0] and employee[3] >= 100000],
    )

if __name__ == '__main__':
    main()
