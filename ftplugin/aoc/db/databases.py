from aoc.db.oracle import Orela
class Default(object):
    def get(*args):
        return Orela()

default_connection = Default()

