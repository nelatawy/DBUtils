import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from visualization.relational.relationalmapper import *
import graphviz
import itertools


class RelationalVisualizer:
    """Render a normalized relational schema into a graphviz diagram.

    Assumptions:
        - `TableRegistry` has already been populated via `fromSchema()` and contains `tables` and `refs` built from the schema model.
        - Each `Table` contains the primary key list in `p_key` and the visible attributes in `attribs`.
        - Reference edges are already normalized such that every relation has a source and destination table and attribute lists.

    Expected behaviour:
        - Tables are rendered as HTML tables with primary keys underlined.
        - Foreign-key references are drawn as edges, collapsing direct one-column joins and splitting multi-column references through junction nodes.

    Raises:
        - `AttributeError`: if `graph` does not support `node` or `edge` calls.
        - `KeyError` / `ValueError`: if registry entries or reference attribute lists do not match the expected shape.
    """

    def __init__(self, graph: graphviz.Digraph):
        self.graph = graph
        self._junction_ids = itertools.count()

    def visualize_table(self, table: Table) -> None:
        """Render a single relational table as a graphviz HTML table node.

        Assumptions:
            - Table attribute names are unique within the table so they can be used as HTML port names.
            - Primary keys are identified via `table.p_key` and are expected to be a subset of `table.attribs`.

        Raises:
            - `AttributeError`: if the graph cannot render nodes.
        """
        cells = []
        pkey = set(table.p_key)
        for attr in table.attribs:
            text = attr
            if attr in pkey:
                text = f"<U>{text}</U>"
            cells.append(f'<TD PORT="{attr}">{text}</TD>')

        label_html = (
            '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="6">'
            f'<TR><TD COLSPAN="{len(table.attribs)}" BGCOLOR="#dddddd"><B>{table.name}</B></TD></TR>'
            f'<TR>{"".join(cells)}</TR>'
            '</TABLE>>'
        )
        self.graph.node(table.name, label_html)

    def visualize_reference(self, reference: Reference) -> None:
        """Render a foreign-key relationship between two tables.

        Assumptions:
            - A reference may be either a single-column direct link or a composite FK represented by multiple columns.
            - If the mapping is recursive, the same table appears as both source and destination; the graph still connects the ports as a self-reference.

        Raises:
            - `AttributeError`: if the graph cannot create edges.
            - `ValueError`: if the reference does not include any source or destination attributes.
        """
        src, dst = reference.source_table.name, reference.dest_table.name

        if len(reference.source_attrib) == 1:
            if reference.source_table == reference.dest_table:
                self.graph.edge(f"{src}:{reference.source_attrib[0]}:s",
                                f"{dst}:{reference.dest_attrib[0]}:s")
            else:
                self.graph.edge(f"{src}:{reference.source_attrib[0]}:s",
                                f"{dst}:{reference.dest_attrib[0]}:n")
            return

        n = next(self._junction_ids)
        s_j, d_j = f"js_{n}", f"jd_{n}"

        self.graph.node(s_j, shape="point", width="0.08", label="")
        self.graph.node(d_j, shape="point", width="0.08", label="")

        for attr in reference.source_attrib:
            self.graph.edge(f"{src}:{attr}:s", s_j, arrowhead="none")
        for attr in reference.dest_attrib:
            self.graph.edge(f"{dst}:{attr}:s", d_j, arrowhead="none")

        self.graph.edge(s_j, d_j)

    def visualize_db(self, table_reg: TableRegistry) -> None:
        """Render every table and foreign-key reference in a registry.

        Assumptions:
            - `table_reg.tables` is a dictionary of normalized tables and `table_reg.refs` contains valid `Reference` entries.
            - The `graph` has already been configured for the desired layout and styling.

        Raises:
            - `AttributeError`: if the registry or graph is not in the required shape.
        """
        for table in table_reg.tables.values():
            self.visualize_table(table)
        for ref in table_reg.refs:
            self.visualize_reference(ref)
