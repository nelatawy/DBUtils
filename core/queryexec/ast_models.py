
class AtomicNode:
    def __init__(self, val):
        self.val = val

class UnaryNode:
    def __init__ (self, op : str, node, extra):
        self.operator = op
        self.first = node
        self.extra = extra

class BinaryNode:
    def __init__ (self, op : str, first, second, extra = None):
        self.operator = op
        self.first = first
        self.second = second
        self.extra =extra


def print_ast(node, indent: str = "", is_last: bool = True) -> None:
    """
    Recursively print the abstract syntax tree in a readable format.
    """
    if node is None:
        return

    # Select the branch marker for this position.
    marker = "└── " if is_last else "├── "
    
    # 1. Identify the node and its content.
    if isinstance(node, AtomicNode):
        print(f"{indent}{marker}AtomicNode: '{node.val}'")
        return  # Leaf nodes have no children.
        
    elif isinstance(node, UnaryNode):
        print(f"{indent}{marker}UnaryNode: [{node.operator}]")
        # Set indentation for the child.
        next_indent = indent + ("    " if is_last else "│   ")
        # Traverse the single operand branch.
        print_ast(node.first, next_indent, is_last=True)
        
    elif isinstance(node, BinaryNode):
        print(f"{indent}{marker}BinaryNode: [{node.operator}]")
        # Set indentation for both children.
        next_indent = indent + ("    " if is_last else "│   ")
        # Traverse the left branch, which is not last.
        print_ast(node.first, next_indent, is_last=False)
        # Traverse the right branch, which is last.
        print_ast(node.second, next_indent, is_last=True)


