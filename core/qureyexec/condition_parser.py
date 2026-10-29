from ast_models import *

class ConditionParser:

    @staticmethod
    def parse(condition : str):

        def parse_atomic(condition : str):
            # binary conditions only [ ==, > , <, >= , <= , != ]
            parts = condition.split(" ")
            return BinaryNode(parts[1], AtomicNode(parts[0]), AtomicNode(parts[2]))
        
        def parse_and(condition : str):
            parts = condition.split(" AND ")
            res = parse_atomic(parts[0])
            for i in range(1, len(parts)):
                res = BinaryNode("AND", res, parse_atomic(parts[i]))
            return res
        
        parts = condition.split(" OR ")

        res = parse_and(parts[0])
        for i in range(1, len(parts)):
            res = BinaryNode("OR", res, parse_and(parts[i]))

        return res                   


def print_ast(node, indent: str = "", is_last: bool = True) -> None:
    """
    Recursively crawls and pretty-prints the Abstract Syntax Tree.
    """
    if node is None:
        return

    # Choose the correct branch marker based on position
    marker = "└── " if is_last else "├── "
    
    # 1. Determine Node Identity and Content
    if isinstance(node, AtomicNode):
        print(f"{indent}{marker}AtomicNode: '{node.name}'")
        return  # Leaf node, no children to crawl
        
    elif isinstance(node, UnaryNode):
        print(f"{indent}{marker}UnaryNode: [{node.operator}]")
        # Prepare the indentation for the child
        next_indent = indent + ("    " if is_last else "│   ")
        # Crawl down the single operand child branch
        print_ast(node.first, next_indent, is_last=True)
        
    elif isinstance(node, BinaryNode):
        print(f"{indent}{marker}BinaryNode: [{node.operator}]")
        # Prepare the indentation for left and right children
        next_indent = indent + ("    " if is_last else "│   ")
        # Crawl the left branch (not the last child of this level)
        print_ast(node.first, next_indent, is_last=False)
        # Crawl the right branch (the last child of this level)
        print_ast(node.second, next_indent, is_last=True)





def main():
    root = ConditionParser.parse("EMPLOYEE.id == lol AND antsh == \"Lolz\"")
    print_ast(root)

if __name__ =='__main__':
    main()
        

