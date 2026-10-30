# we will use climbing precedence
from enum import Enum
from core.queryexec.ast_models import *
from core.queryexec.conditions.condition_parser import ConditionParser
class OpType(Enum):
    UNARY=1
    BINARY=2

class Associativity(Enum):
    RTL=1
    LTR=2



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
        return op.split("[")[0].split("{")[0]

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

        token = []
        option_depth = 0

        def append_token():
            if token:
                tokens.append("".join(token))
                token.clear()

        for char in query:
            if char in "[{":
                option_depth += 1
                token.append(char)
            elif char in "]}":
                option_depth -= 1
                token.append(char)
            elif option_depth == 0 and char.isspace():
                append_token()
            elif option_depth == 0 and char in "()":
                append_token()
                tokens.append(char)
            else:
                token.append(char)

        append_token()

        return tokens


    @staticmethod
    def parse(query : str):
        tokens = QueryParser.__tokenize(query)
        itr = 0

        def consume_token() -> str:
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
                
                extra = None
                if "[" in op:
                    extra = ConditionParser.parse(op.split("[")[1][:-1])
                    op = op.split("[")[0]
                elif "{" in op:
                    extra = op.split("{")[1][:-1].split(",")
                    op = op.split("{")[0]

                return UnaryNode(op, operand, extra)
            
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
                
                condition = None
                try:
                    condition = ConditionParser.parse(op.split("[")[1][:-1])
                except:
                    pass

                left = BinaryNode(op.split("[")[0], left, right, condition)
            return left


        root = parse_expression(min_precedence=0)
        return root


def main():
    node = QueryParser.parse("EMPLOYEE JOIN[emp_id==mgr_id] DEPARTMENT")
    print_ast(node)

if __name__ == '__main__':
    main()



        