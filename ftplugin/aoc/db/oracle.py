import random
import time

class Oracle(object):
    pass


class Orela(object):
    description = [
        ['A', 1, 2, 3],
        ['B', 1, 2, 3],
        ['C', 1, 2, 3],
        ['D', 1, 2, 3],
        ['E', 1, 2, 3],
    ]

    def cursor(self):
        return self

    def fetchmany(self, a):
        return self.execute(None)

    def execute(self, query):
        # real queries take a while to run, mimic that
        time.sleep(random.random()*3)
        return [[int(random.random()*10) or None for x in range(5)] for j in range(50)]

