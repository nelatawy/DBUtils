
from core.queryexec.query.query_exec import MappedTable, QueryExecuter
from core.queryexec.query.query_parser import QueryParser


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


def check_query(evaluator, name, query, expected_attributes, expected_rows):
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


def main():
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
        [
            [10, "Engineering", "Seattle"],
            [20, "Research", "Boston"],
            [30, "Operations", "Austin"],
        ],
    )
    archived_employees = make_table(
        "ArchivedEmployees",
        ["employee_id", "name", "dept_id", "salary"],
        [[101, "Ada", 10, 120000], [104, "Dia", 30, 70000]],
    )

    evaluator = QueryExecuter()
    for table in (employees, departments, archived_employees):
        evaluator.add_table(table)

    employee_names = ["employee_key", "employee_name", "employee_dept_id", "annual_salary"]
    department_names = ["department_id", "department_name", "department_city"]
    archive_names = ["archived_employee_key", "archived_name", "archived_dept_id", "archived_salary"]

    # Each test is a query string, exercising parsing and evaluation together.
    check_query(
        evaluator,
        "PROJECT selects named columns",
        "PROJECT{name,salary} Employees",
        ["name", "salary"],
        [["Ada", 120000], ["Ben", 90000], ["Cy", 80000], ["Dia", 70000]],
    )
    check_query(
        evaluator,
        "SELECT filters rows",
        "SELECT[salary >= 90000] Employees",
        employees.attribs,
        [employees.rows[0], employees.rows[1]],
    )
    check_query(
        evaluator,
        "RENAME changes every column name",
        f"RENAME{{{','.join(employee_names)}}} Employees",
        employee_names,
        employees.rows,
    )
    check_query(
        evaluator,
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
        evaluator,
        "JOIN uses renamed non-overlapping columns",
        employee_department_join,
        employee_names + department_names,
        expected_join_rows,
    )

    check_query(
        evaluator,
        "UNION combines compatible tables",
        "Employees UNION ArchivedEmployees",
        employees.attribs,
        employees.rows + archived_employees.rows,
    )
    check_query(
        evaluator,
        "INTERSECT returns shared rows",
        "Employees INTERSECT ArchivedEmployees",
        employees.attribs,
        [row for row in employees.rows if row in archived_employees.rows],
    )
    check_query(
        evaluator,
        "DIFFERENCE returns unshared rows",
        "Employees DIFFERENCE ArchivedEmployees",
        employees.attribs,
        [row for row in employees.rows if row not in archived_employees.rows],
    )
    check_query(
        evaluator,
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
        evaluator,
        "Nested RENAME + JOIN + SELECT + PROJECT",
        three_table_query,
        ["employee_name", "department_name", "archived_name"],
        expected_three_table_rows,
    )


if __name__ == "__main__":
    main()
