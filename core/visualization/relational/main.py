import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.visualization.relational.relational_mapper import TableRegistry
from visualization.relational.visualization import RelationalVisualizer
from core.visualization.schema_models import Schema

import graphviz

def main():
    test_json = ""
    with open("/home/nelatawy/Projects/DBVisualizer/tests/04_participation.json", "r") as f:
        test_json = f.read()

    schema: Schema = None
    try:
        schema = Schema.model_validate_json(test_json)
    except Exception as e:
        print("An error occured during parsing" + str(e))
        return

    table_reg: TableRegistry = TableRegistry()
    table_reg.from_schema(schema)
    for name in table_reg.tables:
        print(name + str(table_reg.tables[name].attribs))

    graph = graphviz.Digraph()

    graph.attr('node', shape="plain", fontname='Helvetica,Arial,sans-serif', fontsize='10')
    graph.attr('edge', fontname='Helvetica,Arial,sans-serif', fontsize='10')
    graph.attr(rankdir="TB", splines="polyline", nodesep="0.9", ranksep="1.2")

    RelationalVisualizer(graph).visualize_db(table_reg)
    graph.view()

if __name__ == '__main__':
    main()