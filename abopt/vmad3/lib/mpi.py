from abopt.vmad3 import operator, autooperator
from abopt.vmad3.core.model import Literal
import numpy

@operator
class allreduce:
    ain = [('x', '*')]
    aout = [('y', '*')]

    def apl(self, x, comm):
        return comm.allreduce(x)

    def vjp(self, _y, comm):
        return dict(_x = _y)

    def jvp(self, x_, comm):
        return dict(y_ = comm.allreduce(x_))

