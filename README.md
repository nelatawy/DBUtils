# Natural Language ERD Generator

This project aims to provide a tool that people can use to generate proper ERDs from a system description written in natural language and validating aginst deterministic schema constraints.

## Features

- Natural-language database schema generation
- Entity and relationship modeling
- Support for primary keys, composite attributes, derived attributes, and multivalued attributes
- Weak entity recognition and identifying relationship support
- ER diagram visualization output

## Used Libraries

- Pydantic
- Graphviz
- Google GenAI / Gemini
- python-dotenv


## Core Components

### `main.py`

This is the entry point of the application. It loads environment variables, configures the Gemini client, prompts the user for a natural-language database specification, validates the model output, and renders the generated ER diagram.

### `models.py`

This file defines the schema structure used throughout the project. It contains the core data models for attributes, entities, relationships, and the overall schema, along with validation rules to enforce database modeling constraints such as weak entities and relationship cardinality.

### `visualization.py`

This module transforms the validated schema into a Graphviz diagram. It creates nodes for entities, attributes, and relationships, applies styling for derived, multivalued, composite, and primary key attributes, and connects the components into a readable ER diagram.

## Usage

Run the application:

```bash
python main.py
```

Then enter a natural-language description of the system you want to model. The app will produce a structured schema and open the generated ER diagram.

## Example Input

```text
An e-commerce company manages an inventory tracking system where a product category is a strong entity because it exists independently with its own unique category code, while an item variant is a weak entity because it cannot exist without its parent category and only uses a simple color code as a partial identifier. The relationship connecting them is an identifying relationship called categorizes, where a single product category maps to multiple item variants, meaning that if a category is deleted from the database, all its associated variants are automatically wiped out as well.
```

## Example Output

![alt text](image.png)

## Configuration

### Environment Variables

| Variable | Description |
| --- | --- |
| `GENAI_API_KEY` | Google AI API key for schema generation |

## How It Works

1. The user provides a natural-language description of the database.
2. The AI model interprets the system requirements.
3. The schema is validated against the project’s data models.
4. The ER diagram is generated and rendered with Graphviz.

## Analysis Approach

The visualization happens in a straightforward top-down pass. It starts from the full schema, creates each entity node, then adds the entity's attributes as child nodes, and recursively expands any composite or nested attributes before finishing with the relationship nodes. Each relationship is then tied back to the already created entity nodes using the correct cardinality and participation metadata.

This structure keeps the graph readable: the schema is the root, entities are the main blocks, attributes describe each entity, composites break into smaller nested parts, and relationships connect the already-built nodes into a complete ER diagram. A key detail in the graph generation is how name collisions are resolved: the internal node names use the full hierarchy, such as `Entity.Attribute.Child`, while the displayed label stays simple. This allows repeated attribute names to exist within different entities without creating ambiguous graph nodes.

## Model Overview

The schema is built around a few core abstractions:

- `Attribute`: stores the attribute name and metadata such as primary key, partial key, derived status, multivalued status, and nested composite sub-attributes.
- `Entity`: represents a database object and includes its list of attributes and weak-entity metadata.
- `Link`: captures one participating entity in a relationship together with its cardinality and participation type.
- `Relationship`: defines the relationship name, the participating links, and any identifying relationship metadata.
- `Schema`: aggregates the complete set of entities and relationships and validates the overall consistency of the database model.

This separation keeps the project modular: the model layer enforces constraints, the visualization layer renders those constraints, and the application layer orchestrates input, AI generation, and output.

