# we will use climbing precedence
from enum import Enum

class OpType(Enum):
    UNARY=1
    BINARY=2

class Associativity(Enum):
    RTL=1
    LTR=2


class AtomicNode:
    def __init__(self, name : str):
        self.name = name

class UnaryNode:
    def __init__ (self, op : str, node):
        self.operator = op
        self.first = node

class BinaryNode:
    def __init__ (self, op : str, first, second):
        self.operator = op
        self.first = first
        self.second = second


class QueryParser:
    
    operators : dict = {
        "SELECT"    : [OpType.UNARY , Associativity.RTL, 3],
        "PROJECT"   : [OpType.UNARY , Associativity.RTL, 3],
        "JOIN"      : [OpType.BINARY, Associativity.LTR, 2],
        "UNION"     : [OpType.BINARY, Associativity.LTR, 1],
        "INTERSECT" : [OpType.BINARY, Associativity.LTR, 2],
        "DIFFERENCE": [OpType.BINARY, Associativity.LTR, 1],
        "AGGREGATE" : [OpType.UNARY , Associativity.RTL, 3]
    }

    def __get_wout_options(op : str):
        return op.split("[")[0]

    def __get_type(op : str):
        op = QueryParser.__get_wout_options(op)
        return QueryParser.operators[op][0]

    def __get_assoc(op : str):
        op = QueryParser.__get_wout_options(op)
        return QueryParser.operators[op][1]

    def __get_precedence(op : str):
        op = QueryParser.__get_wout_options(op)
        return QueryParser.operators[op][2]

    def __is_operator(op : str):
        return QueryParser.__get_wout_options(op) in QueryParser.operators


    @staticmethod
    def __tokenize(query : str):
        tokens = []

        for tok in query.split(" "):
            base_itr = 0
            scan_itr = 0
            while scan_itr < len(tok):
                if tok[scan_itr] == '(' or tok[scan_itr] == ')':
                    if scan_itr - base_itr > 0:
                        tokens.append(tok[base_itr:scan_itr])

                    tokens.append(tok[scan_itr])
                    base_itr = scan_itr + 1
                
                if tok[scan_itr] == ']':
                    # end of params for operator
                    tokens.append(tok[base_itr:scan_itr + 1])
                    base_itr = scan_itr + 1   

                scan_itr += 1
            
            if scan_itr - base_itr > 0:
                tokens.append(tok[base_itr:scan_itr]) 

        return tokens


    @staticmethod
    def parse(query : str):
        tokens = QueryParser.__tokenize(query)
        itr = 0

        def consume_token():
            nonlocal itr
            itr += 1
            return tokens[itr - 1]

        def peek_token():
            return tokens[itr]

        def has_next():
            return itr < len(tokens)
        
        def parse_primary():
            tok = peek_token()
            if QueryParser.__is_operator(tok):
                # unary operator consume operator and operand
                op = consume_token()
                operand = parse_primary()
                return UnaryNode(op, operand)
            
            elif tok == "(":
                # takes first paren, and swallows the last one and returns whats in between
                consume_token()
                inner = parse_expression(min_precedence=0)
                consume_token()
                return inner
            else:
                # atomic
                var = consume_token()
                return AtomicNode(var)

        def parse_expression(min_precedence : int):
            nonlocal itr
            left = parse_primary()
            while has_next():
                tok = peek_token()
                if not QueryParser.__is_operator(tok) or \
                    QueryParser.__get_precedence(tok) < min_precedence:
                    break
                op = consume_token()

                op_assoc = QueryParser.__get_assoc(op)
                op_prec = QueryParser.__get_precedence(op)

                next_prec = op_prec if op_assoc == Associativity.RTL else op_prec + 1
                right = parse_expression(min_precedence= next_prec)
                left = BinaryNode(op, left, right)
            return left


        root = parse_expression(min_precedence=0)
        return root


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
    node = QueryParser.parse("EMPLOYEE JOIN[emp_id==mgr_id] DEPARTMENT")
    print_ast(node)

if __name__ == '__main__':
    main()



        