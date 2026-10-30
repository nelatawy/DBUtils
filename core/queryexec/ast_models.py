
class AtomicNode:
    def __init__(self, val):
        self.val = val

class UnaryNode:
    def __init__ (self, op : str, node):
        self.operator = op
        self.first = node

class BinaryNode:
    def __init__ (self, op : str, first, second):
        self.operator = op
        self.first = first
        self.second = second