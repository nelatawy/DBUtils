# DBVisualizer

A schema-driven database design toolkit that takes a **single, validated JSON description of a system** and renders it as **two different views of the same design**:

1. **The conceptual layer (ERD):** the classic textbook Entity-Relationship diagram, with rectangles, ellipses, diamonds, underlined keys, double borders for weak entities, and so on.
2. **The logical layer (Relational):** the implementation-level relational model, with tables, primary keys, foreign keys, multivalued attributes split into their own tables, and M:N / n-ary relationships resolved into junction tables.

Both layers are fed by the same Pydantic-validated schema object. Nothing in the relational layer re-parses or re-validates the input, because by the time it runs, the input has already been proven valid.

---

## Table of Contents

- [Features](#features)
- [Architecture and Philosophy](#architecture-and-philosophy)
- [Project Structure](#project-structure)
- [Layer 1: ERD Module](#layer-1-erd-module)
- [Layer 2: Relational Module](#layer-2-relational-module)
  - [The adapter: `relationalmapper.py`](#the-adapter-relationalmapperpy)
  - [The registry: `TableRegistry`](#the-registry-tableregistry)
  - [Order of operations](#order-of-operations)
  - [Mapping to the seven-step algorithm](#mapping-to-the-seven-step-algorithm)
  - [Foreign-key naming](#foreign-key-naming)
  - [The visualizer: `visualization.py`](#the-visualizer-visualizationpy)
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

---

## Architecture and Philosophy

The project is built around one idea: **each stage does exactly one job and knows as little as possible about the others.**

```
   JSON / natural language
            │
            ▼
   ┌─────────────────┐
   │     models      │  Pydantic: parse + validate. Produces a Schema object.
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
| **Validation** | `models` (Pydantic) | Draw anything, or know how tables are built |
| **Transformation** | `relationalmapper` | Validate input, or know anything about Graphviz |
| **Data representation** | `Table`, `Reference`, `TableRegistry` | Contain logic about how to draw themselves |
| **Rendering** | `visualization` | Decide where foreign keys go, or what a junction table is |
| **Orchestration** | `main.py` | Contain any business logic: it only wires the stages together |

The practical consequences:

- **The mapper has no idea Graphviz exists.** You can swap the renderer for SVG, Mermaid, SQL DDL generation, or a test assertion without touching the mapping rules.
- **The visualizer has no idea how the mapping was derived.** It only sees finished tables and references. It never decides whether a column is an FK, it is simply told.
- **The mapping logic can be unit-tested without rendering.** Build a `Schema`, run `fromSchema()`, then assert on `registry.tables` and `registry.refs`.
- **The ERD layer and the relational layer are siblings, not parent and child.** Both consume the same validated `Schema`. Neither imports the other.

### Trust boundary: validate once, at the edge

All validation happens in the `models` module. Entities must have keys, weak entities must have identifying relationships, cardinalities must be legal, and links must refer to entities that exist. Because the relational mapper only ever receives a `Schema` that has already passed those checks, it deliberately **does not re-validate**. Its docstrings state their assumptions explicitly ("the schema has already been validated and all participating entities exist"), and the few `ValueError`s it raises guard against *misuse of an individual conversion method* (for example calling `addOneToOne` on a 1:N relationship), not against bad user data.

This keeps the mapper short and readable, and it keeps the error story simple: bad input fails early and in one place.

---

## Project Structure

```
DBVisualizer/
├── README.md
├── requirements.txt
├── core/
│   ├── models.py                   # Pydantic schema models
│   └── visualization/
│       ├── erd/
│       │   ├── main.py             # Gemini-backed ERD entry point
│       │   └── visualization.py    # ERDVisualizer: Schema → Graphviz
│       └── relational/
│           ├── relationalmapper.py # Schema → relational tables + references
│           ├── visualization.py    # RelationalVisualizer: registry → Graphviz
│           └── main.py             # Relational entry point / manual test driver
├── tests/                          # JSON schema examples
└── image.png                       # Example rendered ERD
```

This tree omits local/generated items such as `.venv/`, `.env`, `__pycache__/`, and `backup.zip`.

---

## Layer 1: ERD Module

The ERD module turns a validated `Schema` into a textbook Entity-Relationship diagram.

### Schema models: `core/models.py`

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

### The adapter: `relationalmapper.py`

`relationalmapper.py` is an **adapter** between the conceptual world (`models`) and the logical world (tables and keys). It imports the Pydantic models, consumes them read-only, and produces its own independent, plain-Python data structures. After conversion, nothing downstream depends on Pydantic at all.

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
| `addEntity` | Base table for an entity: flatten composites, skip derived attributes, defer multivalued ones, record the primary key |
| `addIdentifying` | Weak entity handling: pull the owner's key into the weak entity and record the FK reference |
| `addOneToOne` | Binary 1:1: place one FK |
| `addOneToMany` | Binary 1:N: place the FK on the N side |
| `addManyToMany` | Binary M:N: create a junction table |
| `addNary` | Degree ≥ 3: create a relationship table (also used for n-ary identifying relationships) |
| `addMultiValued` | Separate table for a multivalued attribute, keyed by its owner's key |
| `fromSchema` | The orchestrator: decides the order and dispatches each relationship to the right method |

Because each rule is isolated, adding or changing one (say, a different 1:1 placement strategy) means editing one method.

Internally, `__flattenAttrib` recursively expands composite attributes into atomic column names using a prefix scheme (`Address` with parts `City` and `Street` becomes `Address_City`, `Address_Street`; deeper nesting keeps extending the prefix).

### Order of operations

`fromSchema()` is deliberately **not** a single loop over relationships. The order exists to guarantee that every method finds the data it depends on already in place:

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
| 1 | Regular entity types | `addEntity` | Composites flattened to atomic columns; derived attributes are not stored; multivalued attributes deferred to step 6; the key attribute becomes `p_key` |
| 2 | Weak entity types | `addEntity` (shell) + `addIdentifying` | The owner's primary key is added to the weak entity as FK columns and a `Reference` back to the owner is recorded |
| 3 | Binary 1:1 | `addOneToOne` | FK goes on the side with **total participation**, as the textbook recommends, so it never needs to be null; relationship attributes follow the FK |
| 4 | Binary 1:N | `addOneToMany` | FK goes on the **N side** and references the primary key of the 1 side; relationship attributes follow the FK |
| 5 | Binary M:N | `addManyToMany` | New table named after the relationship; primary key is the union of both FK column sets; relationship attributes become extra columns; two `Reference`s are recorded |
| 6 | Multivalued attributes | `addMultiValued` | New table `<Owner>_<attr>s` holding the owner's key plus the attribute's columns; all columns form the primary key; `Reference` back to the owner |
| 7 | N-ary relationships | `addNary` | New table with one FK group per participating entity; primary key is all FK columns; a `Reference` per participant |

**Where the code deliberately differs from the textbook's presentation order:**

- The textbook lists the steps 1 to 7 in sequence. The code runs step 6 *last* and interleaves steps 3, 4, 5, and 7 per relationship, because the textbook describes the rules conceptually while an implementation has to respect data dependencies (a multivalued table needs its owner's final key).
- Step 2 is split across two moments: the weak entity's table is created with the strong entities (step 1's pass), and its key is completed later by `addIdentifying`. This is why identifying relationships are resolved before everything else.
- Relationship-level multivalued attributes are handled inside steps 3 to 5 and 7 rather than as a separate pass.

### Foreign-key naming

FK column names are produced by one function, `_fk_name`, so the convention lives in a single place:

- If the relationship `Link` has a **role**, the column is `<role>_<target_key>` (for example `supervisor_SSN`).
- Otherwise it falls back to `<entity>_<target_key>`.

Roles are what make recursive relationships work: an `Employee` supervising an `Employee` yields `supervisor_SSN` referencing `SSN` in the same table, and a prerequisite relationship between two `Course` links yields two distinct, readable columns (`prereq_Code`, `dependent_Code`).

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

---

## Usage

Install dependencies (Python 3.10+ and the Graphviz system binary are required):

```bash
pip install pydantic graphviz python-dotenv google-genai
```

**Relational diagram from a JSON schema:**

```python
import graphviz
from models import Schema
from visualization.relational.relationalmapper import TableRegistry
from visualization.relational.visualization import RelationalVisualizer

schema = Schema.model_validate_json(open("tests/04_participation.json").read())

registry = TableRegistry()
registry.fromSchema(schema)          # ERD model → relational model

graph = graphviz.Digraph()
graph.attr("node", shape="plain", fontname="Helvetica,Arial,sans-serif", fontsize="10")
graph.attr(rankdir="TB", splines="polyline", nodesep="0.9", ranksep="1.2")

RelationalVisualizer(graph).visualize_db(registry)
graph.view()
```

You can also stop at the registry and inspect the result without rendering anything:

```python
for name, table in registry.tables.items():
    print(name, table.attribs, "PK:", table.p_key)
for ref in registry.refs:
    print(ref.source_table.name, ref.source_attrib, "->", ref.dest_table.name, ref.dest_attrib)
```

## Configuration

| Variable | Description |
|---|---|
| `GENAI_API_KEY` | Google AI API key. Only needed for the optional natural-language schema generation |

---

## Known Limitations

- **Line style:** Graphviz cannot do true orthogonal ("Manhattan") routing while also attaching to specific ports, so relational edges use polyline splines.
- **Weak-entity keys (binary case):** for binary identifying relationships, the owner's key is added to the weak entity as FK columns and referenced, but the weak entity's `p_key` is not extended with them. The n-ary path does extend it.
- **Single key attribute:** `addEntity` records one key attribute (flattened if composite) as the primary key. Composite keys are expressed through a composite attribute.
---

## Used Libraries

- Pydantic: schema models and validation
- Graphviz: diagram rendering
- Google GenAI / Gemini: optional natural-language schema generation
- python-dotenv: environment configuration
