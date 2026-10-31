# DBUtils

A database toolkit with two independent halves: **visualizing a database's design** and **evaluating relational algebra over its data**.

1. **Visualization:** takes a **single, validated JSON description of a system** and renders it as **two different views of the same design**:
   - **The conceptual layer (ERD):** the classic textbook Entity-Relationship diagram, with rectangles, ellipses, diamonds, underlined keys, double borders for weak entities, and so on.
   - **The logical layer (Relational):** the implementation-level relational model, with tables, primary keys, foreign keys, multivalued attributes split into their own tables, and M:N / n-ary relationships resolved into junction tables.
2. **Relational algebra evaluation:** takes table data as JSON and a **relational-algebra query string** (`SELECT`, `PROJECT`, `RENAME`, `JOIN`, `UNION`, `INTERSECT`, `DIFFERENCE`, `AGGREGATE`), parses it into an AST and executes it, returning the resulting table. See [Module 2: Query Execution](#module-2-query-execution).

The visualization modules draw the *structure* of a database; the query execution module works on its *contents*. They share no code and do not import each other. Within the visualization half, both layers are fed by the same Pydantic-validated schema object, and nothing in the relational layer re-parses or re-validates the input, because by the time it runs, the input has already been proven valid.

---

## Table of Contents

- [Features](#features)
- [Architecture and Philosophy](#architecture-and-philosophy)
- [Project Structure](#project-structure)
- [Layer 1: ERD Module](#layer-1-erd-module)
- [Layer 2: Relational Module](#layer-2-relational-module)
  - [The adapter: `relational_mapper.py`](#the-adapter-relational_mapperpy)
  - [The registry: `TableRegistry`](#the-registry-tableregistry)
  - [Order of operations](#order-of-operations)
  - [Mapping to the seven-step algorithm](#mapping-to-the-seven-step-algorithm)
  - [Foreign-key naming](#foreign-key-naming)
  - [The visualizer: `visualization.py`](#the-visualizer-visualizationpy)
- [Module 2: Query Execution](#module-2-query-execution)
  - [Pipeline overview](#pipeline-overview)
  - [Separation of concerns](#separation-of-concerns-1)
  - [Input data: `state_models.py`](#input-data-state_modelspy)
  - [The AST: `ast_models.py`](#the-ast-ast_modelspy)
  - [Query language](#query-language)
  - [Query parser: precedence climbing](#query-parser-precedence-climbing)
  - [Condition language, parser and evaluator](#condition-language-parser-and-evaluator)
  - [Execution: `query_exec.py`](#execution-query_execpy)
  - [Operator reference](#operator-reference)
  - [Errors](#errors)
  - [Running the self-tests](#running-the-self-tests)
- [Usage](#usage)
- [Configuration](#configuration)
- [Known Limitations](#known-limitations)
- [Used Libraries](#used-libraries)

---

## Features

**Shared**

- One JSON schema format drives both diagrams
- Strict validation with Pydantic before anything is drawn
- Support for primary keys, partial keys, composite, derived, and multivalued attributes
- Weak entities and identifying relationships
- Binary and n-ary relationships with cardinality and participation constraints

**ERD layer**

- Textbook ER diagram output via Graphviz
- Natural-language schema generation (optional): describe a system in plain English and have a Gemini model produce the JSON schema, which is then validated like any hand-written input

**Relational layer**

- Automatic ERD-to-relational mapping following the standard textbook algorithm (Elmasri & Navathe)
- Composite attributes flattened into atomic columns
- Multivalued attributes moved into their own tables
- M:N and n-ary relationships resolved into junction tables
- Foreign keys placed on the correct side and named deterministically
- Relational diagram output via Graphviz: tables with per-column ports, FK edges that can link single columns or groups of columns

**Query execution module**

- Relational-algebra query strings such as `PROJECT{emp_name,dept_name} SELECT[pay >= 100000] (RENAME{emp_id,emp_name,emp_dept,pay} Employees JOIN[emp_dept == dept_id] Departments)`
- Table data supplied as JSON and validated with Pydantic (uniform columns and types per table)
- Eight operators: `SELECT`, `PROJECT`, `RENAME`, `JOIN` (theta and natural), `UNION`, `INTERSECT`, `DIFFERENCE`, `AGGREGATE` (`MAX`, `MIN`, `AVG`)
- Precedence-climbing query parser that builds an AST, with a separate parser for the conditions inside `SELECT[...]` / `JOIN[...]`
- Parsers, evaluators and table operations are fully decoupled: the executor never sees query text, and the parsers never see data

---

## Architecture and Philosophy

The project is built around one idea: **each stage does exactly one job and knows as little as possible about the others.**

```
   JSON / natural language
            │
            ▼
   ┌─────────────────┐
  │  schema_models  │  Pydantic: parse + validate. Produces a Schema object.
   └────────┬────────┘
            │  validated Schema
            ├──────────────────────────────┐
            ▼                              ▼
   ┌─────────────────┐            ┌──────────────────┐
   │  ERD visualizer │            │ relational mapper│  Adapter: Schema → TableRegistry
   └────────┬────────┘            └────────┬─────────┘
            ▼                              │  TableRegistry (tables + refs)
      textbook ERD                         ▼
                                  ┌──────────────────┐
                                  │ relational       │
                                  │ visualizer       │
                                  └────────┬─────────┘
                                           ▼
                                  relational diagram
```

### Separation of concerns

| Concern | Where it lives | What it does *not* do |
|---|---|---|
| **Validation** | `core/visualization/schema_models.py` (Pydantic) | Draw anything, or know how tables are built |
| **Transformation** | `core/visualization/relational/relational_mapper.py` | Validate input, or know anything about Graphviz |
| **Data representation** | `Table`, `Reference`, `TableRegistry` | Contain logic about how to draw themselves |
| **Rendering** | `visualization` | Decide where foreign keys go, or what a junction table is |
| **Orchestration** | `main.py` | Contain any business logic: it only wires the stages together |

The practical consequences:

- **The mapper has no idea Graphviz exists.** You can swap the renderer for SVG, Mermaid, SQL DDL generation, or a test assertion without touching the mapping rules.
- **The visualizer has no idea how the mapping was derived.** It only sees finished tables and references. It never decides whether a column is an FK, it is simply told.
- **The mapping logic can be unit-tested without rendering.** Build a `Schema`, run `from_schema()`, then assert on `registry.tables` and `registry.refs`.
- **The ERD layer and the relational layer are siblings, not parent and child.** Both consume the same validated `Schema`. Neither imports the other.

### Trust boundary: validate once, at the edge

All validation happens in `core/visualization/schema_models.py`. Entities must have keys, weak entities must have identifying relationships, cardinalities must be legal, and links must refer to entities that exist. Because the relational mapper only ever receives a `Schema` that has already passed those checks, it deliberately **does not re-validate**. Its docstrings state their assumptions explicitly ("the schema has already been validated and all participating entities exist"), and the few `ValueError`s it raises guard against *misuse of an individual conversion method* (for example calling `add_one_to_one()` on a 1:N relationship), not against bad user data.

This keeps the mapper short and readable, and it keeps the error story simple: bad input fails early and in one place.

---

## Project Structure

```
DBUtils/
├── README.md
├── requirements.txt
├── core/
│   ├── visualization/
│   │   ├── schema_models.py            # Pydantic schema models
│   │   ├── erd/
│   │   │   ├── main.py                 # Gemini-backed ERD entry point
│   │   │   └── visualization.py        # ERDVisualizer: Schema → Graphviz
│   │   └── relational/
│   │       ├── relational_mapper.py    # Schema → relational tables + references
│   │       ├── visualization.py        # RelationalVisualizer: registry → Graphviz
│   │       └── main.py                 # Relational entry point / manual test driver
│   └── queryexec/                      # Module 2: relational-algebra query execution
│       ├── state_models.py             # Pydantic models for incoming table data
│       ├── ast_models.py               # AtomicNode / UnaryNode / BinaryNode + print_ast
│       ├── query/
│       │   ├── query_exec.py           # MappedTable, TableUtils, QueryExecuter
│       │   ├── main.py                 # Runnable query examples and smoke tests
│       │   └── query_parser.py         # QueryParser: query string → AST (precedence climbing)
│       └── conditions/
│           ├── condition_parser.py     # ConditionParser: condition string → AST
│           └── condition_eval.py       # ConditionEvaluater: condition AST + values → bool
├── tests/                              # JSON schema examples
└── image.png                           # Example rendered ERD
```

This tree omits local/generated items such as `.venv/`, `.env`, `__pycache__/`, and `backup.zip`.

---

## Layer 1: ERD Module

The ERD module turns a validated `Schema` into a textbook Entity-Relationship diagram.

### Schema models: `core/visualization/schema_models.py`

Defines the Pydantic schema types consumed by both diagram layers:

- `Attribute`: name plus metadata (primary key, partial key, derived, multivalued, nested composite sub-attributes)
- `Entity`: a named collection of attributes, with weak-entity metadata
- `Link`: one participating entity in a relationship, with its cardinality, participation type, and optional role
- `Relationship`: name, participating links, its own attributes, and an `identifies` list
- `Schema`: the full set of entities and relationships, with checks for duplicate entity names, unknown relationship participants, and weak entities not named in any `identifies` list

Entity attributes and relationship attributes are `Attribute` objects. Composite attributes may contain nested `Attribute` objects or strings. The models enforce such constraints as requiring a key for each non-weak entity and a minimum degree of two for relationships; the ERD renderer itself assumes it receives validated model instances.

### ERD rendering: `core/visualization/erd/visualization.py`

`ERDVisualizer` receives a configured Graphviz `Digraph` and a validated `Schema`. It creates entity boxes (double-bordered for weak entities), attribute ovals, and relationship diamonds (double-bordered when `identifies` is non-empty). Primary-key labels are underlined, partial-key labels are marked with underlines, derived attributes use dashed outlines, and multivalued attributes use double outlines. Composite attributes are expanded recursively and connected to their component nodes.

Relationship edges are labeled with each link's cardinality and visually distinguish total participation and links to identified entities through edge color styling. The renderer creates entity and attribute nodes before relationship edges. Attribute node identifiers include their parent path, such as `Entity.Attribute.Child`, to avoid collisions between repeated attribute names.

### Natural-language input (Gemini-backed entry point)



The current ERD entry point, `core/visualization/erd/main.py`, prompts for a natural-language system description and asks Gemini to produce JSON using `Schema` as the response schema. It then parses the response with `Schema.model_validate_json` before rendering. This entry point currently follows the Gemini path; the JSON-file example in the source is commented-out test code, not an active CLI option. Set `GENAI_API_KEY` to use it.

**Example input**

```text
An e-commerce company manages an inventory tracking system where a product category is a strong entity because it exists independently with its own unique category code, while an item variant is a weak entity because it cannot exist without its parent category and only uses a simple color code as a partial identifier. The relationship connecting them is an identifying relationship called categorizes, where a single product category maps to multiple item variants, meaning that if a category is deleted from the database, all its associated variants are automatically wiped out as well.
```

**Example output**

![ERD example output](image.png)

---

## Layer 2: Relational Module

The relational module lives in `core/visualization/relational/` and has two files with two distinct responsibilities: **one transforms, one draws.**

### The adapter: `relational_mapper.py`

`core/visualization/relational/relational_mapper.py` is an **adapter** between the conceptual world (`schema_models.py`) and the logical world (tables and keys). It imports the Pydantic models, consumes them read-only, and produces its own independent, plain-Python data structures. After conversion, nothing downstream depends on Pydantic at all.

It defines three small classes:

| Class | Role |
|---|---|
| `Table` | A relational table: a `name`, a flattened `p_key` list, and an ordered `attribs` list (atomic columns, flattened composites, and any FK columns added later) |
| `Reference` | A foreign-key relationship: a source table and source column list pointing at a destination table and destination column list, in matching order |
| `TableRegistry` | The container and the conversion engine: holds `tables` (name → `Table`) and `refs` (list of `Reference`), and knows how to populate them from a `Schema` |

Everything the renderer needs is in `tables` and `refs`. That is the entire contract between the two files.

### The registry: `TableRegistry`

`TableRegistry` is both the **result** of the conversion and the **builder** that produces it. Each textbook rule is a small, single-purpose method:

| Method | Responsibility |
|---|---|
| `add_entity()` | Base table for an entity: flatten composites, skip derived attributes, defer multivalued ones, record the primary key |
| `add_identifying()` | Weak entity handling: pull the owner's key into the weak entity and record the FK reference |
| `add_one_to_one()` | Binary 1:1: place one FK |
| `add_one_to_many()` | Binary 1:N: place the FK on the N side |
| `add_many_to_many()` | Binary M:N: create a junction table |
| `add_nary()` | Degree ≥ 3: create a relationship table (also used for n-ary identifying relationships) |
| `add_multi_valued()` | Separate table for a multivalued attribute, keyed by its owner's key |
| `from_schema()` | The orchestrator: decides the order and dispatches each relationship to the right method |

Because each rule is isolated, adding or changing one (say, a different 1:1 placement strategy) means editing one method.

Internally, `__flatten_attrib()` recursively expands composite attributes into atomic column names using a prefix scheme (`Address` with parts `City` and `Street` becomes `Address_City`, `Address_Street`; deeper nesting keeps extending the prefix).

### Order of operations

`from_schema()` is deliberately **not** a single loop over relationships. The order exists to guarantee that every method finds the data it depends on already in place:

1. **Create all entity tables.** Strong entities get their full key; weak entities get a shell holding only their partial key. Composites are flattened, derived attributes dropped, and multivalued attributes skipped for now. Every table that any later step may reference now exists in `self.tables`.
2. **Resolve identifying relationships first.** Weak entities cannot be referenced or extended until the owner's key has been absorbed, so these run before anything else that might point at a weak entity.
3. **Resolve standard relationships.** Each is dispatched on its shape:
   - two links, both cardinality `1` → one-to-one
   - two links, exactly one `1` → one-to-many
   - two links, neither `1` → many-to-many
   - more than two links → n-ary
4. **Resolve entity multivalued attributes last.** A multivalued table copies its owner's primary key, so it must wait until that key is final, including any key columns absorbed in steps 2 and 3.

Multivalued attributes that belong to a *relationship* are handled inline by whichever method creates or extends the table that holds that relationship's attributes.

### Mapping to the seven-step algorithm

The standard ERD-to-relational procedure in *Fundamentals of Database Systems* (Elmasri & Navathe) has seven steps. Here is how each one maps onto the code:

| # | Textbook step | Implementation | Notes |
|---|---|---|---|
| 1 | Regular entity types | `add_entity()` | Composites flattened to atomic columns; derived attributes are not stored; multivalued attributes deferred to step 6; the key attribute becomes `p_key` |
| 2 | Weak entity types | `add_entity()` (shell) + `add_identifying()` | The owner's primary key is added to the weak entity as FK columns and a `Reference` back to the owner is recorded |
| 3 | Binary 1:1 | `add_one_to_one()` | FK goes on the side with **total participation**, as the textbook recommends, so it never needs to be null; relationship attributes follow the FK |
| 4 | Binary 1:N | `add_one_to_many()` | FK goes on the **N side** and references the primary key of the 1 side; relationship attributes follow the FK |
| 5 | Binary M:N | `add_many_to_many()` | New table named after the relationship; primary key is the union of both FK column sets; relationship attributes become extra columns; two `Reference`s are recorded |
| 6 | Multivalued attributes | `add_multi_valued()` | New table `<Owner>_<attr>s` holding the owner's key plus the attribute's columns; all columns form the primary key; `Reference` back to the owner |
| 7 | N-ary relationships | `add_nary()` | New table with one FK group per participating entity; primary key is all FK columns; a `Reference` per participant |

**Where the code deliberately differs from the textbook's presentation order:**

- The textbook lists the steps 1 to 7 in sequence. The code runs step 6 *last* and interleaves steps 3, 4, 5, and 7 per relationship, because the textbook describes the rules conceptually while an implementation has to respect data dependencies (a multivalued table needs its owner's final key).
- Step 2 is split across two moments: the weak entity's table is created with the strong entities (step 1's pass), and its key is completed later by `add_identifying()`. This is why identifying relationships are resolved before everything else.
- Relationship-level multivalued attributes are handled inside steps 3 to 5 and 7 rather than as a separate pass.

### Foreign-key naming

FK column names are produced by one function, `_fk_name`, so the convention lives in a single place:

- If the relationship `Link` has a **role**, the column is `<role>_<target_key>` (for example `supervisor_SSN`).
- Otherwise it falls back to `<entity>_<target_key>`.

Roles are what make recursive relationships work: an `Employee` supervising an `Employee` yields `supervisor_SSN` referencing `SSN` in the same table, and a prerequisite relationship between two `Course` links yields two distinct, readable columns (`prereq_Code`, `dependent_Code`).

The diagram below shows exactly these cases as rendered by the relational visualizer. `Employee` and `Person` each carry a self-referencing foreign key (`supervisor_SSN`, `supervisor_NationalID`), drawn as a loop under the table. `Prerequisite_Of` is a junction table whose two key columns, `prereq_Code` and `dependent_Code`, both reference `Course.Code`.


### The visualizer: `visualization.py`

`RelationalVisualizer` takes a Graphviz `Digraph` and a populated `TableRegistry` and draws it. It contains **no mapping logic**: it renders what it is given.

**Tables** are drawn as Graphviz HTML-like labels (`shape="plain"`):

- A title cell spanning all columns, then one cell per column side by side
- Primary-key columns underlined
- Each column cell has a `PORT` equal to the column name, so edges can attach to a specific attribute rather than to the table as a whole

**References** are drawn as edges between those ports:

- **Single-column FK:** a direct edge from the FK cell to the referenced cell (bottom of the source to top of the destination)
- **Composite FK:** a point-shaped junction node on each side. Every FK column connects to the source junction, every referenced column connects to the destination junction, and one arrow connects the two junctions. This gives the "group of attributes references a group of attributes" look without ambiguity about which columns belong together
- **Self-reference:** bottom-to-bottom, so the loop forms underneath the table instead of crossing the title cell

Junction nodes get unique IDs from an `itertools.count()` owned by the visualizer instance, so two references between the same pair of tables never merge into one.

**Order of operations in `visualize_db`:** all tables first, then all references. Every port an edge mentions already exists by the time the edge is created.

The caller owns graph-level styling (direction, spacing, fonts, spline style). `main.py` configures a top-to-bottom layout with polyline splines before handing the graph to the visualizer, which keeps presentation choices out of the rendering class.

**Example output**

Below is a relational diagram for a small company schema. Underlined columns are primary keys, and each arrow runs from a foreign-key column to the column it references. `Employee` and `Project` each reference `Department`, `Office` references `Employee`, and `Works_On` is the junction table that resolves the M:N relationship between `Employee` and `Project`; its primary key is the union of its two foreign keys.

---

## Module 2: Query Execution

The query execution module lives in `core/queryexec/`. It takes a **relational-algebra query as a string** and a **database supplied as JSON**, and returns the resulting table. It is independent of the diagram modules above: it has its own models, its own parsers and no dependency on Graphviz or on the ERD `Schema`.

```text
SELECT[salary >= 100000] Employees
PROJECT{name,salary} Employees
RENAME{emp_id,emp_name,emp_dept,pay} Employees
Employees JOIN[dept_id] Departments
RENAME{emp_id,emp_name,emp_dept,pay} Employees JOIN[emp_dept == dept_id] Departments
PROJECT{emp_name,dept_name} SELECT[pay >= 100000] (RENAME{emp_id,emp_name,emp_dept,pay} Employees JOIN[emp_dept == dept_id] Departments)
```

Columns are always referred to by their plain names, so two tables that share a column name have to be told apart with `RENAME` before they are joined (see [Operator reference](#operator-reference)).

### Pipeline overview

Two independent inputs flow through separate stages and only meet in the executor:

```
   JSON database state             query string
           │                             │
           ▼                             ▼
   ┌───────────────┐             ┌───────────────┐
   │  state_models │             │  QueryParser  │  ◄── ConditionParser
   │   (Pydantic)  │             │  (precedence  │      (parses the [...] options)
   └───────┬───────┘             │   climbing)   │
           │ DatabaseState       └───────┬───────┘
           ▼                             │ AST
   ┌───────────────┐                     │
   │  MappedTable  │                     │
   │   (adapter)   │                     │
   └───────┬───────┘                     │
           └──────────────┬──────────────┘
                          ▼
              ┌───────────────────────┐
              │     QueryExecuter     │  uses TableUtils
              │    (walks the AST)    │  and ConditionEvaluater
              └───────────┬───────────┘
                          ▼
              MappedTable (the result)
```

### Separation of concerns

The same rule as the rest of the project applies: **each stage does one job and knows as little as possible about the others.**

| Concern | Where it lives | What it does *not* do |
|---|---|---|
| **Validation of incoming data** | `state_models.py` (Pydantic) | Evaluate queries, or know what a query is |
| **Parsing a query** | `QueryParser` | Look at any data, evaluate a condition, or execute anything |
| **Parsing a condition** | `ConditionParser` | Evaluate it. It only produces an AST |
| **Evaluating a condition** | `ConditionEvaluater` | Know how the AST was built. It receives an AST and a dictionary of values |
| **Table operations** | `TableUtils` | Parse anything, or know about queries. Each method is a pure function of tables (and a condition AST) |
| **Working data representation** | `MappedTable` | Validate input. It is an adapter from the Pydantic form to a plain list-based form |
| **Execution** | `QueryExecuter` | Care how the AST was constructed. It walks nodes and dispatches on `node.operator` |

The practical consequences:

- **Parsers only parse.** `QueryParser` and `ConditionParser` return ASTs and nothing else. You can test them with `print_ast` without any table data.
- **Evaluators only evaluate.** `ConditionEvaluater.evaluate(ast, values)` takes a condition AST plus a `{name: value}` dictionary. `QueryExecuter.evaluate(ast)` takes a query AST. Neither knows or cares whether the AST came from a parser or was assembled by hand; the self-tests exercise query parsing and execution together.
- **Pydantic stays at the edge.** `MappedTable` converts a validated `TableState` into plain lists once, so the operators never touch Pydantic types. The two forms can change independently.
- **Adding an operator touches three places only:** the `operators` table in `QueryParser`, a new method in `TableUtils`, and one new branch in `QueryExecuter.evaluate`.

### Input data: `state_models.py`

Incoming JSON is validated with three Pydantic `RootModel`s:

| Model | Shape | Role |
|---|---|---|
| `Row` | `Dict[str, Any]` | One record: column name → value |
| `TableState` | `List[Row]` | One table. A validator enforces a **uniform schema** |
| `DatabaseState` | `Dict[str, TableState]` | The whole database: table name → table |

Example input:

```json
{
  "Employees": [
    {"employee_id": 101, "name": "Ava Chen",   "dept_id": 10, "salary": 128000},
    {"employee_id": 102, "name": "Noah Patel", "dept_id": 20, "salary": 96000}
  ],
  "Departments": [
    {"dept_id": 10, "dept_name": "Engineering", "city": "Seattle"},
    {"dept_id": 20, "dept_name": "Research",    "city": "Boston"}
  ]
}
```

`TableState`'s `enforce_uniform_schema` validator uses the **first row as the baseline** and requires every other row to have exactly the same column names, **in the same order**, with the same Python **type** for each column. A mismatch raises a `ValueError` tagged `"schema_mismatch"` that names the offending row index (Pydantic wraps it in a `ValidationError`). Empty tables pass validation. Note that types are compared strictly, so a column holding `1` in one row and `1.5` in another (`int` vs `float`) is rejected.

Validating here is what lets everything downstream assume that a table is rectangular and that each column has one type, so the operators contain no per-row type checks.

### The AST: `ast_models.py`

Both the query parser and the condition parser produce the same three node types, so one printer and one set of conventions covers both:

| Node | Fields | Used for |
|---|---|---|
| `AtomicNode` | `val` | A table name in a query, or an attribute name / literal in a condition |
| `UnaryNode` | `operator`, `first`, `extra` | `SELECT`, `PROJECT`, `RENAME`, `AGGREGATE`: one operand |
| `BinaryNode` | `operator`, `first`, `second`, `extra` | `JOIN`, `UNION`, `INTERSECT`, `DIFFERENCE` in queries; comparison operators and `AND` / `OR` in conditions |

`extra` carries the operator's **options**:

| Operator | `extra` holds |
|---|---|
| `SELECT[cond]` | a condition AST |
| `JOIN[cond]` | a condition AST (or an `AtomicNode` for a natural join), or `None` |
| `PROJECT{a,b}` | a list of column names |
| `RENAME{x,y,...}` | a list of new column names |
| `AGGREGATE{MAX(a),...}` | a list of aggregation expressions |
| `UNION`, `INTERSECT`, `DIFFERENCE` | `None` |

`print_ast(node)` prints any tree in a readable box-drawing format, which is the quickest way to check how a query was understood:

```text
>>> print_ast(QueryParser.parse("PROJECT{name} SELECT[salary > 5] (A UNION B)"))
└── UnaryNode: [PROJECT]
    └── UnaryNode: [SELECT]
        └── BinaryNode: [UNION]
            ├── AtomicNode: 'A'
            └── AtomicNode: 'B'
```

(`print_ast` shows operator structure only; the `extra` options are not printed.)

### Query language

A query is an expression over **table names** and **operators**. Operators carry their options directly attached to the operator token, with no space between the keyword and the bracket:

| Operator | Kind | Syntax | Options |
|---|---|---|---|
| `SELECT` | unary, prefix | `SELECT[condition] operand` | a [condition](#condition-language-parser-and-evaluator) in `[ ]` |
| `PROJECT` | unary, prefix | `PROJECT{col1,col2} operand` | comma-separated columns in `{ }` |
| `RENAME` | unary, prefix | `RENAME{new1,new2,...} operand` | one new name per column, in the table's column order, in `{ }` |
| `AGGREGATE` | unary, prefix | `AGGREGATE{MAX(col),MIN(col),AVG(col)} operand` | comma-separated `FUNC(col)` in `{ }` |
| `JOIN` | binary, infix | `left JOIN[condition] right` or `left JOIN[attr] right` | a condition, or the one attribute name the tables share for a natural join |
| `UNION` | binary, infix | `left UNION right` | none |
| `INTERSECT` | binary, infix | `left INTERSECT right` | none |
| `DIFFERENCE` | binary, infix | `left DIFFERENCE right` | none |

Parentheses group sub-expressions. Operators are case-sensitive. Whitespace around the items in a `{ }` option list is ignored, so `PROJECT{name, salary}` and `RENAME{a, b, c}` work the same as the compact form.

**Precedence and associativity**

| Level | Operators | Associativity |
|---|---|---|
| 3 (tightest) | `SELECT`, `PROJECT`, `RENAME`, `AGGREGATE` | right-to-left (prefix) |
| 2 | `JOIN`, `INTERSECT` | left-to-right |
| 1 (loosest) | `UNION`, `DIFFERENCE` | left-to-right |

Two things follow from this and are worth knowing when writing queries:

- `A UNION B JOIN[...] C` parses as `A UNION (B JOIN C)`, because `JOIN` binds tighter than `UNION`.
- A unary operator applies to **the next operand only**, not to a whole binary expression. To select over a join, parenthesize the join: `SELECT[salary > 5] (A JOIN[...] B)`. Without parentheses, `SELECT[...] A JOIN[...] B` means `(SELECT[...] A) JOIN[...] B`.
- The same rule is what makes joins of renamed tables read naturally: `RENAME{...} A JOIN[...] RENAME{...} B` renames `A` and `B` separately and then joins them. To rename a *result*, parenthesize it: `RENAME{...} (A JOIN[...] B)`.

### Query parser: precedence climbing

`query/query_parser.py` builds the AST using **precedence climbing**, driven by the single `operators` table at the top of `QueryParser` (type, associativity, precedence per operator). The grammar rules live in that data rather than in the control flow.

**1. Tokenizing.** The query is split on whitespace and parentheses, except that anything inside `[ ]` or `{ }` stays attached to its operator token. This means a condition can contain spaces (`SELECT[salary >= 100000]` is one token) while `Employees JOIN[...] Departments` still splits into three. A bracket-depth counter handles this.

**2. `parse_primary`** handles the things that bind tightest:

- an **operator token**: consume it, parse its operand with `parse_primary`, then attach its options (the text between the brackets goes to `ConditionParser`, or is split on commas for `{ }`) and return a `UnaryNode`
- `(`: parse a full expression with `min_precedence=0`, then consume the closing `)`
- anything else: a table name, returned as an `AtomicNode`

**3. `parse_expression(min_precedence)`** is the climbing loop. It parses a primary as the left side, then, while the next token is an operator with precedence ≥ `min_precedence`, it consumes the operator and parses the right side with a higher minimum (`prec + 1` for left-associative operators, `prec` for right-associative ones). This is what makes left-associative chains group correctly (`A UNION B UNION C` is `(A UNION B) UNION C`) and lets higher-precedence operators bind first. Options on a binary operator, such as a `JOIN` condition, are parsed into the `extra` field of the resulting `BinaryNode`.

The parser produces a tree and nothing more. It never looks at a table, never checks that a table exists, and never evaluates a condition.

### Condition language, parser and evaluator

Conditions appear inside `SELECT[...]` and `JOIN[...]`.

**Building blocks**

A condition is made of comparisons, optionally combined with `AND` / `OR`.

| Piece | Form | Example |
|---|---|---|
| Comparison | `attribute OP value` | `salary >= 100000` |
| Combination | `condition AND condition`, `condition OR condition` | `age > 40 AND city == "Boston"` |
| Natural-join key | a single attribute name (`JOIN` only) | `Employees JOIN[dept_id] Departments` |

**Comparison operators:** `==`, `!=`, `>`, `>=`, `<`, `<=`

**What can go on each side of a comparison**

| Side | Allowed | Examples |
|---|---|---|
| Left | an attribute name | `salary`, `emp_dept` |
| Right | a number | `100000` (parsed as a float, so it compares fine against integer columns) |
| Right | a double-quoted string | `"John Smith"` |
| Right | another attribute name | `dept_id` |

An unquoted word on the right is always looked up as an attribute, never treated as a string.

**Rules**

- `AND` binds tighter than `OR`: `a AND b OR c` means `(a AND b) OR c`.
- There are no parentheses and no `NOT`.
- Parts are separated by spaces, so **spaces are required around the operator**: `salary >= 100000`, not `salary>=100000`.
- Names are plain column names. There is no `Table.column` qualification, so when two tables being joined share a column name, `RENAME` one side first.

**`ConditionParser`** (`conditions/condition_parser.py`) splits on `OR`, then on `AND`, then parses each atom. Quoted literals are split out first, so spaces inside a string such as `"John Smith"` are preserved. It returns an AST of `BinaryNode`s: leaf comparisons are `BinaryNode(op, AtomicNode(left), AtomicNode(right))`, combined by `BinaryNode("AND" | "OR", ...)`. A single-token condition returns a bare `AtomicNode`, which `JOIN` interprets as a natural join.

**`ConditionEvaluater`** (`conditions/condition_eval.py`) takes a condition AST and a dictionary mapping names to values, and returns a boolean:

```python
ast = ConditionParser.parse('EMPL.name == "John Smith" AND EMPL.age > 40')
ConditionEvaluater.evaluate(ast, {"EMPL.name": "John Smith", "EMPL.age": 45})   # True
```

It recurses through `AND` / `OR` nodes and evaluates each comparison leaf by looking the left name up in the dictionary and resolving the right side as a quoted literal, a number, or another dictionary lookup. Because the evaluator only ever receives a dictionary, it has no knowledge of tables or rows: the caller decides what names are in scope. `TableUtils` builds that dictionary once per row (or per row pair, for joins).

### Execution: `query_exec.py`

Three classes, each with one job.

**`MappedTable`** is the adapter between the validated Pydantic form and the working form. It holds a `name`, an ordered `attribs` list of column names, and `rows` as a list of plain lists aligned with `attribs`. Operators create their results through `set_attributes` and `add_row`, so a result is just another `MappedTable` and can feed the next operator. `SELECT`, `PROJECT` and `RENAME` keep the name of their input table; the results of `JOIN`, `UNION`, `INTERSECT`, `DIFFERENCE` and `AGGREGATE` are unnamed (`name == ""`).

**`TableUtils`** holds the logic of each operation as a static method: `select_from_table`, `project_table`, `rename_attributes`, `join_tables`, `union_tables`, `intersect_tables`, `difference_table`, `aggregate_table`. Each takes `MappedTable`s (plus a condition AST where relevant) and returns a new `MappedTable`. Nothing is mutated and nothing here knows about parsing or query strings.

**`QueryExecuter`** is the registry and the evaluator:

- `add_table(table)` registers a named `MappedTable` (a non-empty name is required)
- `evaluate(node)` walks the query AST recursively. An `AtomicNode` is looked up by name in the registry. For operator nodes it evaluates the operand(s) first, then dispatches on `node.operator` to the matching `TableUtils` method, passing `node.extra` as the options

Because `evaluate` only reads `operator`, `first`, `second` and `extra`, it is completely indifferent to how the tree was built.

### Operator reference

| Operator | Result columns | Result rows | Notes |
|---|---|---|---|
| `SELECT[cond] T` | all columns of `T` | rows of `T` for which `cond` is true | Column names are the evaluation scope, e.g. `salary >= 100000` |
| `PROJECT{a,b} T` | the listed columns, **in `T`'s column order** | the kept columns of each row of `T`, with **duplicate rows removed** (first occurrence kept, original row order preserved) | Names that do not exist in `T` are ignored |
| `RENAME{n1,...,nk} T` | `n1,...,nk` in place of `T`'s columns, **matched by position** | all rows of `T`, unchanged | Needs exactly one new name per column of `T`, otherwise `ValueError`. Keeps `T`'s name |
| `A JOIN[cond] B` (theta) | all columns of `A`, then all columns of `B` | every `A`×`B` pair for which `cond` is true | `A` and `B` must share **no column names** (use `RENAME`). A `JOIN` with no `[...]` condition returns no rows |
| `A JOIN[attr] B` (natural) | `A`'s columns without `attr`, then `attr`, then `B`'s columns without `attr` | pairs where `A.attr == B.attr`, the join value appearing once | `attr` must be in both tables and be the **only** column they share |
| `A UNION B` | `A`'s columns | all rows of `A` followed by all rows of `B` | Duplicates are kept (like SQL `UNION ALL`). Columns must match exactly |
| `A INTERSECT B` | `A`'s columns | distinct rows of `A` that are also in `B`, in `A`'s order (first occurrence kept) | Set semantics. Columns must match exactly |
| `A DIFFERENCE B` | `A`'s columns | distinct rows of `A` not in `B`, in `A`'s order (first occurrence kept) | Set semantics. Columns must match exactly |
| `AGGREGATE{...} T` | one column per expression, named like `MAX(salary)` | a single row | Supports `MAX`, `MIN`, `AVG`; no grouping |

**Column names in joins.** Conditions refer to columns by plain name; there is no `Table.column` qualification. To keep every name unambiguous, a theta join requires the two inputs to share no column names, and a natural join requires the join attribute to be the only name they share. When tables overlap, rename them first:

```text
RENAME{emp_id,emp_name,emp_dept,pay} Employees JOIN[emp_dept == dept_id] Departments
```

**Union compatibility.** `UNION`, `INTERSECT` and `DIFFERENCE` require `first.attribs == second.attribs`: same names, same order.

### Errors

| Situation | What happens |
|---|---|
| Data violates the uniform-schema rule | Pydantic `ValidationError` at load time (`"schema_mismatch"`, with the row index) |
| Query references an unregistered table | `KeyError` from `QueryExecuter.evaluate` |
| Condition references a name not in scope | `KeyError` from `ConditionEvaluater` |
| Natural join on an attribute missing from either table, or on tables that share other columns too | `ValueError` |
| Theta join between tables that share any column name | `ValueError` (rename first) |
| `RENAME` with a different number of names than columns | `ValueError` |
| `UNION` / `INTERSECT` / `DIFFERENCE` on incompatible tables | `ValueError` |
| Aggregating a column that does not exist, or a malformed `FUNC(col)` | `ValueError` |
| Unsupported aggregate function (e.g. `SUM`) | `ValueError`, but only on tables with at least two rows (see Known Limitations) |
| `add_table()` with an empty name | `ValueError` |
| Unknown operator reaching `evaluate` | `ValueError` ("Unsupported query operator") |

### Running the self-tests

`core/queryexec/query/main.py` builds three small tables (`Employees`, `Departments`, `ArchivedEmployees`) and checks the result of every operator. Every check is a **query string**, so parsing and execution are always exercised together. Results are compared as multisets of rows, so the order of rows does not matter. The checks cover `PROJECT`, `SELECT`, `RENAME` (on two tables), a theta `JOIN` between two renamed tables, `UNION`, `INTERSECT`, `DIFFERENCE`, `AGGREGATE`, and a final query that renames three tables, joins them, then applies `SELECT` and `PROJECT`.

```bash
python -m core.queryexec.query.main
```

Each check prints `PASS: <name> (<n> rows)` and an assertion error identifies the failing operator. The parsers also have small demos you can run the same way (`python -m core.queryexec.query.query_parser`, `python -m core.queryexec.conditions.condition_eval`).

> The self-tests build tables with `set_attributes()` / `add_row()` and only use theta joins, so they do not exercise the `TableState → MappedTable` path or natural joins. Empty tables are the exception, see *Known Limitations → Query execution module*.

---

## Usage

Install dependencies (Python 3.10+ and the Graphviz system binary are required):

```bash
pip install -r requirements.txt
```

**Running a relational-algebra query:**

```python
from core.queryexec.state_models import DatabaseState
from core.queryexec.query.query_parser import QueryParser
from core.queryexec.query.query_exec import QueryExecuter, MappedTable

# db.json: {"Employees":   [{"employee_id": 101, "name": "Ava Chen", "dept_id": 10, "salary": 128000}, ...],
#           "Departments": [{"dept_id": 10, "dept_name": "Engineering", "city": "Seattle"}, ...]}
state = DatabaseState.model_validate_json(open("db.json").read())   # validate once, at the edge

executer = QueryExecuter()
for name, table_state in state.root.items():
    executer.add_table(MappedTable(name, table_state))              # Pydantic form → working form

ast = QueryParser.parse(
    "PROJECT{emp_name,dept_name} SELECT[pay >= 100000] "
    "(RENAME{emp_id,emp_name,emp_dept,pay} Employees "      # RENAME lists every column, by position
    "JOIN[emp_dept == dept_id] Departments)"
)
result = executer.evaluate(ast)
print(result.attribs)      # ['emp_name', 'dept_name']
print(result.rows)
```

## Configuration

| Variable | Description |
|---|---|
| `GENAI_API_KEY` | Google AI API key. Only needed for the optional natural-language schema generation |

---

## Known Limitations

- **Line style:** Graphviz cannot do true orthogonal ("Manhattan") routing while also attaching to specific ports, so relational edges use polyline splines.
- **Weak-entity keys (binary case):** for binary identifying relationships, the owner's key is added to the weak entity as FK columns and referenced, but the weak entity's `p_key` is not extended with them. The n-ary path does extend it.
- **Single key attribute:** `add_entity()` records one key attribute (flattened if composite) as the primary key. Composite keys are expressed through a composite attribute.

**Query execution module**

- **Empty tables have no columns.** `[]` validates and `MappedTable` now loads it, but a JSON array with no rows carries no column names, so `attribs` is `None`. Queries that touch such a table fail with an unhelpful `TypeError` (`'NoneType' object is not subscriptable` for `SELECT`, `'NoneType' object is not iterable` for `PROJECT` and `AGGREGATE`), and `UNION` / `INTERSECT` / `DIFFERENCE` with it raise the compatibility `ValueError`. To use an empty table, build it with `set_attributes` instead.
- **Conditions need spaces around the operator.** `salary >= 100000` works; `salary>=100000` is read as a single token and treated as a natural-join attribute name, so in a `SELECT` it raises no error and **silently matches no rows**. The same applies to `JOIN[a==b]`.
- **No parentheses or `NOT` inside conditions.** `AND` binds tighter than `OR`, evaluated left to right. `AND` / `OR` are found by plain text search, so those words inside a quoted string literal will confuse the parser.
- **Right-hand operands:** numbers (parsed as floats), quoted strings, or attribute names. An unquoted word is always treated as an attribute name, never a string.
- **Unary operators bind to the next operand only.** A binary expression under `SELECT`, `PROJECT` or `AGGREGATE` must be parenthesized.
- **`PROJECT` ignores the order you list and ignores unknown names.** It returns columns in the table's original order, not the order listed, and silently drops any name that is not a column of the table.
- **Mixed duplicate semantics.** `PROJECT`, `INTERSECT` and `DIFFERENCE` use set semantics: duplicates are removed, the first occurrence is kept and the input order is preserved, so results are deterministic. `UNION` is the exception: it keeps duplicate rows (like SQL's `UNION ALL`).
- **`AGGREGATE` is limited** to `MAX`, `MIN` and `AVG` with no grouping; it always returns a single row. `AVG` assumes numeric values. On an empty table every aggregate returns `None`. An unsupported function name (e.g. `SUM`) is only rejected when the table has at least two rows: the first row just seeds the result, so on a one-row table `SUM(x)` returns the value and on an empty table it returns `None`, with no error.
- **Joins need disjoint column names.** There is no `Table.column` qualification, so tables that share a column name must be renamed before a theta join. `RENAME` is positional and total: it must list a new name for every column, and there is no way to rename a single column.
- **`PROJECT`, `INTERSECT` and `DIFFERENCE` need hashable values.** They deduplicate with sets of tuples, so a column holding a list or object (valid in the JSON input) raises `TypeError`.
- **Operators are case-sensitive and upper-case** (`SELECT`, not `select`).

---

## Used Libraries

- Pydantic: schema models and validation
- Graphviz: diagram rendering
- Google GenAI / Gemini: optional natural-language schema generation
- python-dotenv: environment configuration
