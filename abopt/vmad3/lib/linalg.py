from abopt.vmad3 import operator
from abopt.vmad3 import modeloperator
import numpy

@operator
class mul:
    ain = {'x1' : '*',
           'x2' : '*',
          }
    aout = {'y' : '*'}

    def opr(self, x1, x2):
        return dict(y = x1 * x2)

    def vjp(self, _y, x1, x2):
        return dict(_x1 = _y * x2,
                    _x2 = _y * x1)

    def jvp(self, x1_, x2_, x1, x2):
        return dict(y_ = x1_* x2 + x1 * x2_)

@operator
class to_scalar:
    ain  = {'x': 'ndarray'}
    aout = {'y': '*'}

    def opr(self, x):
        return dict(y = (abs(x) ** 2).sum())

    def vjp(self, _y, x):
        return dict(_x = 2. * _y * x)

    def jvp(self, x_, x):
        return dict(y_ = 2. * x_ * x)

@operator
class add:
    ain  = {'x1': '*',
            'x2': '*',
           }
    aout = {'y': '*'}

    def opr(self, x1, x2):
        return dict(y = x1 + x2)

    def vjp(self, _y):
        return dict(_x1 = _y, _x2 = _y)

    def jvp(self, x1_, x2_):
        return dict(y_ = x1_ + x2_)

@operator
class log:
    ain = {'x' : '*',
          }
    aout = {'y' : '*'}

    def opr(self, x):
        return dict(y=numpy.log(x))

    def vjp(self, _y, x):
        return dict(_x = _y * 1 / x)

    def jvp(self, x_, x):
        return dict(y_ = x * 1 / x)

@operator
class pow:
    ain = {'x' : '*',
          }
    aout = {'y' : '*'}

    def opr(self, x, n):
        return dict(y=x ** n)

    def vjp(self, _y, x):
        fac = x ** (n - 1) if n != 1 else 1
        return dict(_x = n * _y * fac)

    def jvp(self, x_, x):
        fac = x ** (n - 1) if n != 1 else 1
        return dict(y_ = n * y_ * fac)

@operator
class copy:
    ain = {'x' : 'ndarray'}
    aout = {'y' : 'ndarray'}

    def opr(self, x, ):
        return dict(y = numpy.copy(x))

    def vjp(self, _y):
        return dict(_x = numpy.copy(_y))

    def jvp(self, x_):
        return dict(y_ = numpy.copy(x_))

@operator
class stack:
    ain = {'x' : 'ndarray',}
    aout = {'y' : 'ndarray'}

    def opr(self, x, axis):
        return dict(y=numpy.stack(x, axis=axis))

    def vjp(self, _y, axis):
        return dict(_x=[numpy.take(_y, i, axis=axis)
                for i in range(numpy.shape(_y)[axis])])

    def jvp(self, x_, axis):
        return dict(y_=numpy.stack(x_, axis))
