
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
    Recursively crawls and pretty-prints the Abstract Syntax Tree.
    """
    if node is None:
        return

    # Choose the correct branch marker based on position
    marker = "└── " if is_last else "├── "
    
    # 1. Determine Node Identity and Content
    if isinstance(node, AtomicNode):
        print(f"{indent}{marker}AtomicNode: '{node.val}'")
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


