from ..ast_models import *

class ConditionParser:

    def is_number(s):
        try:
            float(s)
            return True
        except ValueError:
            return False
        
    @staticmethod
    def __tokenize(condition : str):
                literal_split = condition.split("\"") #get literals first
                parts = []
                # parts with indices 0, 2, 4 etc map to text between literals
                for i in range(len(literal_split)):
                    if not len(literal_split[i]):
                        continue
                    if i % 2 == 1:
                        parts.append("\"" + literal_split[i] + "\"") #add qoutations back
                    else:
                        parts.extend(filter(lambda x : len(x) > 0, literal_split[i].split(" ")))
                return parts
    
    @staticmethod
    def parse(condition : str):
        
        def parse_atomic(condition : str):
            # binary conditions only [ ==, > , <, >= , <= , != ]
            parts = ConditionParser.__tokenize(condition)
            if len(parts) == 1: #used for natural joins
                return AtomicNode(parts[0])
            
            left = AtomicNode(parts[0])
            right = AtomicNode(float(parts[2]) if ConditionParser.is_number(parts[2]) else parts[2])
            return BinaryNode(parts[1], left, right)
        
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


def main():
    root = ConditionParser.parse("EMPLOYEE.id == lol AND antsh == \"Lolz\"")
    print_ast(root)

if __name__ =='__main__':
    main()
        

