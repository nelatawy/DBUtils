import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import graphviz
from core.visualization.schema_models import *


class ERDVisualizer:
    """Render an ER schema as a graphviz diagram.

    Assumptions:
        - The project models have validated the schema, names, and link targets.
        - The supplied `graphviz.Digraph` is already styled.
        - Composite attributes become recursive child nodes.

    Expected behavior:
        - Entities are boxes; weak entities have double borders; attributes are ovals; relationships are diamonds.
        - Relationship attributes are child nodes of their relationship diamonds.

    Raises:
        - `AttributeError`: if `graph` is not Graphviz-like.
        - `TypeError`: if a model object has an unexpected shape.
    """

    def __init__(self, graph: graphviz.Digraph):
        self.graph = graph

    def visualize_simple_attrib(self, node_name: str, attrib: str) -> None:
        """Render a plain attribute node without any model metadata.

        Assumptions:
            - This is used only for string-valued attributes or the leaf elements of composite attributes.

        Raises:
            - `AttributeError`: if the wrapped graph is missing `node`.
        """
        self.graph.node(name=node_name, label=attrib, shape="oval")

    def visualize_attribute(self, node_name: str, attrib: Attribute) -> None:
        """Render a typed attribute node with the project-specific styling.

        Assumptions:
            - Primary keys are underlined, partial keys are stricken, derived attributes are dashed, and multi-valued attributes have a thicker border.
            - Composite attributes are expanded recursively into child nodes.

        Raises:
            - `AttributeError`: if the graph is missing `node` or `edge`.
            - `TypeError`: if `attrib` is not an `Attribute` instance.
        """
        label = attrib.name
        if attrib.is_primary_key:
            label = f"<<U>{label}</U>>"
        elif attrib.is_partial_key:
            label = "".join(c + "\u0332" for c in label)

        self.graph.node(
            name=node_name,
            label=label,
            shape="oval",
            style="dashed" if attrib.is_derived else "solid",
            peripheries="2" if attrib.is_multi_valued else "1",
        )

        if attrib.composite:
            for ele in attrib.composite:
                simple_attrib = isinstance(ele, str)
                child_node_name = f"{node_name}.{ele if simple_attrib else ele.name}"

                if simple_attrib:
                    self.visualize_simple_attrib(child_node_name, ele)
                else:
                    self.visualize_attribute(child_node_name, ele)

                self.graph.edge(node_name, child_node_name, arrowhead='none')

    def visualize_entity(self, entity: Entity) -> None:
        """Render an entity as a boxed node with its attributes connected as children.

        Assumptions:
            - Each entity name is unique in the schema and matches a corresponding model object.
            - Attributes are either strings or `Attribute` objects, matching the schema model contract.

        Raises:
            - `AttributeError`: if the graph cannot accept node or edge calls.
        """
        self.graph.node(
            name=entity.name,
            label=entity.name,
            shape="box",
            peripheries="2" if entity.is_weak else "1",
        )

        for attrib in entity.attributes:
            simple_attrib = isinstance(attrib, str)
            child_node_name = f"{entity.name}.{attrib if simple_attrib else attrib.name}"

            if simple_attrib:
                self.visualize_simple_attrib(child_node_name, attrib)
            else:
                self.visualize_attribute(child_node_name, attrib)

            self.graph.edge(entity.name, child_node_name, arrowhead='none')

    def visualize_relation(self, relation: Relationship) -> None:
        """Render a relationship diamond and attach it to its participating entities.

        Assumptions:
            - Relationship names are unique; link entity names refer to entities already present in the currently rendered graph.
            - Total participation and identifying relationships should be visually emphasized by the chosen edge color strategy.

        Raises:
            - `AttributeError`: if graph methods are unavailable.
            - `ValueError`: if a link object is malformed enough to lack `entity`, `cardinality`, or `participation`.
        """
        self.graph.node(
            name=relation.name,
            label=relation.name,
            shape="diamond",
            peripheries="2" if len(relation.identifies) > 0 else "1",
        )
        identified_entities = set(relation.identifies)

        for link in relation.links:
            self.graph.edge(
                relation.name,
                link.entity,
                label=link.cardinality,
                arrowhead='none',
                color="black:invis:black" if link.entity in identified_entities or link.participation == "total" else "black",
            )

        for attr in relation.attributes:
            child_node_name = f"{relation.name}.{attr.name}"
            self.visualize_attribute(child_node_name, attr)
            self.graph.edge(relation.name, child_node_name, arrowhead='none')

    def visualize_schema(self, schema: Schema) -> None:
        """Render the complete schema into the configured graph.

        Assumptions:
            - This is the top-level pass and assumes all entity and relationship objects are valid according to the schema model.
            - The graph object is already initialized and may be styled externally before invoking this method.

        Raises:
            - `AttributeError`: if the graph is not a graphviz.Digraph instance.
        """
        for entity in schema.entities:
            self.visualize_entity(entity)

        for relation in schema.relationships:
            self.visualize_relation(relation)
