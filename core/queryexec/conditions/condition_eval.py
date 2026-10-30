from .condition_parser import *
from ..ast_models import *
from typing import Dict, Any

class ConditionEvaluater:
    
    def eval_simple_condition(node : BinaryNode, values : Dict[str, Any]):
        op = node.operator
        if not isinstance(node.first, AtomicNode) or not isinstance(node.second, AtomicNode):
            raise ValueError("eval_simple_condition only works on simple conditions")
        
        first = values[node.first.val]
        second = ""
        if isinstance(node.second.val,str):
            if node.second.val[0] == "\"" and node.second.val[-1] == "\"":
                # literal
                second = node.second.val[1:-1]
            else:
                second = values[node.second.val]
        else:
            second = node.second.val

        if   op == "==":
            return first == second
        elif op == "!=":
            return first != second
        elif op == ">":
            return first > second
        elif op == ">=":
            return first >= second
        elif op == "<":
            return first < second
        elif op == "<=":
            return first <= second
        else :
            return False

    @staticmethod
    def evaluate(root, values : Dict[str,Any]):
        if isinstance(root, BinaryNode):
            op = root.operator
            left = ConditionEvaluater.evaluate(root.first, values)
            right = ConditionEvaluater.evaluate(root.second, values)
            if op == "AND":
                return left and right
            elif op == "OR":
                return left or right
            else:
                return ConditionEvaluater.eval_simple_condition(root, values)
        else:
            return False



def main():
    condition = "EMPL.name == \"John Smith\" AND EMPL.age > 40"
    values = {
        "EMPL.name" : "John Smith",
        "EMPL.age" : 45
    }
    ast = ConditionParser.parse(condition)
    print(ConditionEvaluater.evaluate(ast, values))

if __name__ == '__main__':
    main()