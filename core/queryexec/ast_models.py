
class AtomicNode:
    def __init__(self, val):
        self.val = val

class UnaryNode:
    def __init__ (self, op : str, node, condition = None):
        self.operator = op
        self.first = node
        self.condition = condition

class BinaryNode:
    def __init__ (self, op : str, first, second, condition = None):
        self.operator = op
        self.first = first
        self.second = second
        self.condition = condition