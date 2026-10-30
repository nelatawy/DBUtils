import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.visualization.relational.relational_mapper import *
import graphviz
import itertools


class RelationalVisualizer:
    """Render a normalized relational schema as a Graphviz diagram.

    Assumptions:
        - `fromSchema()` has populated `TableRegistry.tables` and `TableRegistry.refs`.
        - Each `Table` stores primary keys in `p_key` and visible columns in `attribs`.
        - Each reference has normalized source and destination tables and attribute lists.

    Expected behavior:
        - Tables render as HTML tables with underlined primary keys.
        - Single-column foreign keys use direct edges; composite references use junction nodes.

    Raises:
        - `AttributeError`: if `graph` lacks `node` or `edge`.
        - `KeyError` / `ValueError`: if registry entries or reference attributes have an unexpected shape.
    """

    def __init__(self, graph: graphviz.Digraph):
        self.graph = graph
        self._junction_ids = itertools.count()

    def visualize_table(self, table: Table) -> None:
        """Render one relational table as a Graphviz HTML-table node.

        Assumptions:
            - Attribute names are unique and can serve as HTML port names.
            - `table.p_key` is a subset of `table.attribs`.

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
            - A reference is a direct single-column link or a composite foreign key.
            - Recursive mappings use the same table as source and destination, connecting its ports as a self-reference.

        Raises:
            - `AttributeError`: if the graph cannot create edges.
            - `ValueError`: if source or destination attributes are missing.
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
            - `table_reg.tables` contains normalized tables and `table_reg.refs` valid references.
            - `graph` is already configured with the desired layout and styling.

        Raises:
            - `AttributeError`: if the registry or graph has an unexpected shape.
        """
        for table in table_reg.tables.values():
            self.visualize_table(table)
        for ref in table_reg.refs:
            self.visualize_reference(ref)
