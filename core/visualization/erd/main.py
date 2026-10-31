import os
from core.visualization.schema_models import *
from core.visualization.erd.visualization import ERDVisualizer
from google import genai
from google.genai import types
import graphviz
from dotenv import load_dotenv
import sys

load_dotenv()

GENAI_SYS_INSTRUCTION = """
You are a professional DataBase designer that should take the description of the system from the user
(client) model the system based on this descrition, identifying primary keys, composite and multivalued attributes,
and relationships both binary and n-ary are supported.
Rules go as follows:
1. Attribute is either a plain string (a simple attribute with no flags) or an object.
2. Attribute object has a required name, optional JSON flags isPrimaryKey, isMultiValued, isDerived (default false), and an optional composite array.
3. composite is an array of attributes (strings or objects), and it nests to any depth, so flags work at any level.
4. Relationship has a required name and a links array. Each entry in links must include: entity (matching a defined entity), cardinality (such as '1', 'N', or 'M'), and participation ('total' or 'partial').
5. WEAK ENTITIES: If an entity depends on another entity for its identity, it is a WEAK ENTITY. 
    - A weak entity MUST NOT have any attribute with 'isPrimaryKey' set to true. Its attributes are just normal strings/objects (acting as partial keys).
   - The relationship connecting the strong entity to the weak entity is an IDENTIFYING RELATIONSHIP. You MUST include the weak entity's name inside that relationship's 'identifies' array.
6. _comment is optional and ignored.
"""

def main():
    # Initialize the Gemini client.
    client = genai.Client(api_key=os.environ.get("GENAI_API_KEY"))
    config = types.GenerateContentConfig(
        system_instruction=GENAI_SYS_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=Schema,
        temperature=0.0
    )

    # Read specifications from standard input.
    print("Write your elaborate system specifications in natural language :)")
    lines = []
    input_str = ""
    while True:
        input_str = input()
        if not input_str:
            break
        lines.append(input_str)
    input_str = "".join(lines)

    # Alternatively, load test input from a file.
    # with open("/home/nelatawy/Projects/DBVisualizer/tests/main_test.json") as f:
    #     input_str = f.read()

    json_input = client.models.generate_content(
        model= "gemini-3.5-flash-lite",
        contents=input_str,
        config=config
    ).text

    print(json_input)
    schema : Schema
    try:
        schema = Schema.model_validate_json(json_input)
    except ValueError as e:
        print(f"An error occured during parsing \n Error : {e}")
        return

    # Render the schema.
    graph = graphviz.Digraph('ER_Diagram', comment='Generated ER Schema')

    # Configure global graph styling.
    graph.attr('node', fontname='Helvetica,Arial,sans-serif', fontsize='10')
    graph.attr('edge', fontname='Helvetica,Arial,sans-serif', fontsize='10')
    graph.attr(rankdir='LR')  # Left-to-Right layout

    ERDVisualizer(graph).visualize_schema(schema)

    graph.view()

if __name__ == "__main__":
    main()
