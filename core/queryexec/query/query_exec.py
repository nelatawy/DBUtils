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

        res_table = MappedTable(table.name, None)
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
        res_table = MappedTable(table.name, None)
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
        overlapping_attribs = (len(set(first.attribs).intersection(second.attribs)))
        
        natural_join = (isinstance(cond_tree, AtomicNode))
        if natural_join:
            join_attrib = cond_tree.val
            if join_attrib not in first.attribs or join_attrib not in second.attribs:
                raise ValueError("Can't perform natural JOIN if tables don't have the JOIN attribute")

            if overlapping_attribs > 1:
                raise ValueError("Can't perform a JOIN on 2 tables having overlapping attributes other than the JOIN attribute")
            
            join_attrib_indices = first.attribs.index(join_attrib), second.attribs.index(join_attrib)
            
            first_wout_join_attr = first.attribs[:]
            first_wout_join_attr.remove(join_attrib)

            second_wout_join_attr = second.attribs[:]
            second_wout_join_attr.remove(join_attrib)

            res_table.set_attributes(first_wout_join_attr + [join_attrib] + second_wout_join_attr)
            
            for row1 in first.rows:
                for row2 in second.rows:
                    if row1[join_attrib_indices[0]] == row2[join_attrib_indices[1]]:
                        first_part = row1[:]
                        first_part.remove(join_attrib)

                        second_part = row2[:]
                        second_part.remove(join_attrib)

                        res_table.add_row(first_part + [join_attrib] + second_part)
        else:
            if overlapping_attribs:
                raise ValueError("Can't perform a theta join on 2 tables with overlapping attrib names perform a\
                                  RENAME first or use a natural join if it's the only overlapping attribute")
            res_table.set_attributes(first.attribs + second.attribs)
            # At this point, columns do not overlap
            for row1 in first.rows:
                values = dict()
                for j in range(len(row1)):
                    values[first.attribs[j]] = row1[j]

                for row2 in second.rows:
                    for j in range(len(row2)):
                        values[second.attribs[j]] = row2[j]

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

    @staticmethod
    def rename_attributes(table : MappedTable, new_names : list[str]):
        if len(new_names) != len(table.attribs):
            raise ValueError("Can't rename attributes if attribute length and new name list length don't match")

        res_table = MappedTable(table.name, None)
        for row in table.rows:
            res_table.add_row(row)
        res_table.set_attributes(new_names)
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
        
        elif node.operator == "RENAME":
            return TableUtils.rename_attributes(first, node.extra)
        
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

    def row_counts(rows):
        counts = {}
        for row in rows:
            key = tuple(row)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def check_query(name, query, expected_attributes, expected_rows):
        result = evaluator.evaluate(QueryParser.parse(query))
        assert result.attribs == expected_attributes, (
            f"{name}\nQuery: {query}\n"
            f"Expected columns: {expected_attributes}\nActual columns: {result.attribs}"
        )
        assert row_counts(result.rows) == row_counts(expected_rows), (
            f"{name}\nQuery: {query}\n"
            f"Expected rows: {expected_rows}\nActual rows: {result.rows}"
        )
        print(f"PASS: {name} ({len(result.rows)} rows)")

    employees = make_table(
        "Employees",
        ["employee_id", "name", "dept_id", "salary"],
        [
            [101, "Ada", 10, 120000],
            [102, "Ben", 20, 90000],
            [103, "Cy", 10, 80000],
            [104, "Dia", 30, 70000],
        ],
    )
    departments = make_table(
        "Departments",
        ["dept_id", "dept_name", "city"],
        [[10, "Engineering", "Seattle"], [20, "Research", "Boston"], [30, "Operations", "Austin"]],
    )
    archived_employees = make_table(
        "ArchivedEmployees",
        ["employee_id", "name", "dept_id", "salary"],
        [[101, "Ada", 10, 120000], [104, "Dia", 30, 70000]],
    )

    evaluator = QueryExecuter()
    for table in (employees, departments, archived_employees):
        evaluator.addTable(table)

    employee_names = ["employee_key", "employee_name", "employee_dept_id", "annual_salary"]
    department_names = ["department_id", "department_name", "department_city"]
    archive_names = ["archived_employee_key", "archived_name", "archived_dept_id", "archived_salary"]

    # Each test is a query string: parsing and evaluation are always exercised together.
    check_query(
        "PROJECT selects named columns",
        "PROJECT{name,salary} Employees",
        ["name", "salary"],
        [["Ada", 120000], ["Ben", 90000], ["Cy", 80000], ["Dia", 70000]],
    )
    check_query(
        "SELECT filters rows",
        "SELECT[salary >= 90000] Employees",
        employees.attribs,
        [employees.rows[0], employees.rows[1]],
    )
    check_query(
        "RENAME changes every column name",
        f"RENAME{{{','.join(employee_names)}}} Employees",
        employee_names,
        employees.rows,
    )
    check_query(
        "RENAME works on a second table",
        f"RENAME{{{','.join(department_names)}}} Departments",
        department_names,
        departments.rows,
    )

    employee_department_join = (
        f"RENAME{{{','.join(employee_names)}}} Employees "
        "JOIN[employee_dept_id == department_id] "
        f"RENAME{{{','.join(department_names)}}} Departments"
    )
    expected_join_rows = [
        employee + department
        for employee in employees.rows
        for department in departments.rows
        if employee[2] == department[0]
    ]
    check_query(
        "JOIN uses renamed non-overlapping columns",
        employee_department_join,
        employee_names + department_names,
        expected_join_rows,
    )

    check_query(
        "UNION combines compatible tables",
        "Employees UNION ArchivedEmployees",
        employees.attribs,
        employees.rows + archived_employees.rows,
    )
    check_query(
        "INTERSECT returns shared rows",
        "Employees INTERSECT ArchivedEmployees",
        employees.attribs,
        [row for row in employees.rows if row in archived_employees.rows],
    )
    check_query(
        "DIFFERENCE returns unshared rows",
        "Employees DIFFERENCE ArchivedEmployees",
        employees.attribs,
        [row for row in employees.rows if row not in archived_employees.rows],
    )
    check_query(
        "AGGREGATE calculates multiple values",
        "AGGREGATE{MAX(salary),MIN(salary),AVG(salary)} Employees",
        ["MAX(salary)", "MIN(salary)", "AVG(salary)"],
        [[120000, 70000, 90000]],
    )

    # Three relations, three inline renames, two joins, then filter and project.
    three_table_query = (
        f"PROJECT{{employee_name,department_name,archived_name}} "
        "SELECT[annual_salary >= 70000] "
        f"((RENAME{{{','.join(employee_names)}}} Employees "
        "JOIN[employee_dept_id == department_id] "
        f"RENAME{{{','.join(department_names)}}} Departments) "
        "JOIN[employee_key == archived_employee_key] "
        f"RENAME{{{','.join(archive_names)}}} ArchivedEmployees)"
    )
    expected_three_table_rows = [
        [employee[1], department[1], archived[1]]
        for employee in employees.rows
        for department in departments.rows
        for archived in archived_employees.rows
        if employee[2] == department[0]
        and employee[0] == archived[0]
        and employee[3] >= 70000
    ]
    check_query(
        "Nested RENAME + JOIN + SELECT + PROJECT",
        three_table_query,
        ["employee_name", "department_name", "archived_name"],
        expected_three_table_rows,
    )

if __name__ == '__main__':
    main()
