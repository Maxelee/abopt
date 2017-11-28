from __future__ import print_function

from pprint import pprint
from abopt.vmad3.operator import add, to_scalar, operator
from abopt.vmad3.model import Builder
import pytest

@operator
class error_on_grad:
    ain = {'x' : '*'}
    aout = {'y' : '*'}

    def apl(self, x):
        return dict(y=x)

    def vjp(self, _y):
        raise AssertionError("shall not reach here")

    def jvp(self, x_):
        raise AssertionError("shall not reach here")

@operator
class error:
    ain = {'x' : '*'}
    aout = {'y' : '*'}

    def apl(self, x):
        raise AssertionError("shall not reach here")

    def vjp(self, _y):
        raise AssertionError("shall not reach here")

    def jvp(self, x_):
        raise AssertionError("shall not reach here")

def test_operator_zero():

    with Builder() as m:
        a = m.input('a')
        t1 = error_on_grad(x=a)
        m.output(c=t1)

    init = dict(a=3)

    c, tape = m.compute(init=init, vout='c', return_tape=True)
    assert c == 3

    vjp = tape.get_vjp()
    init = dict(_c=0)
    _a = vjp.compute(init=init, vout='_a', monitor=print)
    assert _a == 0

    jvp = tape.get_jvp()
    init = dict(a_=0)
    c_ = jvp.compute(init=init, vout='c_', monitor=print)
    assert c_ == 0

def test_operator_skip_unused():

    with Builder() as m:
        a = m.input('a')
        t1 = error(x=a)
        m.output(c=a)

    init = dict(a=3)

    c, tape = m.compute(init=init, vout='c', return_tape=True)
    assert c == 3

    vjp = tape.get_vjp()
    init = dict(_c=0)
    _a = vjp.compute(init=init, vout='_a', monitor=print)
    assert _a == 0

    jvp = tape.get_jvp()
    init = dict(a_=0)
    c_ = jvp.compute(init=init, vout='c_', monitor=print)
    assert c_ == 0

import numpy
@operator
class split:
    ain = {('x', '*')}
    # for python 2.x need to use this syntax
    # to preserve orders
    aout = [('args', '*'),]

    def apl(self, x, axis):
        return dict(args=[numpy.take(x, i, axis=axis) for i in range(numpy.shape(x)[axis])])

    def vjp(self, _args, axis):
        return dict(_x=numpy.stack(_args, axis=axis))

    def jvp(self, x_, axis):
        return dict(args_=[numpy.take(x_, i, axis=axis) for i in range(numpy.shape(x_)[axis])])

@operator
class stack:
    ain = {('args', '*')}
    # for python 2.x need to use this syntax
    # to preserve orders
    aout = [('y', '*'),]

    def apl(self, args, axis):
        return dict(y=numpy.stack(args, axis=axis))

    def vjp(self, _y, args, axis):
        return dict(_args=[numpy.take(_y, i, axis=axis) for i in range(numpy.shape(_y)[axis])])

    def jvp(self, args_, args, axis):
        return dict(y_=numpy.stack(args_, axis))


def test_operator_list_in():
    from numpy.testing import assert_array_equal

    with Builder() as m:
        a = m.input('a')
        t = stack(args=[a, a, a], axis=1)
        m.output(c=t)

    init = dict(a=[1, 2])

    c, tape = m.compute(init=init, vout='c', return_tape=True)
    assert_array_equal(c, [[1, 1, 1], [2, 2, 2]])

    vjp = tape.get_vjp()
    init = dict(_c=[[1, 1, 1], [1, 1, 1]])
    _a = vjp.compute(init=init, vout='_a', monitor=print)

    assert_array_equal(_a, [3, 3])

    jvp = tape.get_jvp()
    init = dict(a_=[1, 1])
    c_ = jvp.compute(init=init, vout='c_', monitor=print)

    assert_array_equal(c_, [[1, 1, 1], [1, 1, 1]])

def test_operator_list_out():
    from numpy.testing import assert_array_equal
    from abopt.vmad3.symbol import List, Symbol

    with Builder() as m:
        a = m.input('a')

        # it is very awkward to prepare a list output
        # I doubt this will be of any usefulness
        b1 = Symbol(m, 'b1')
        b2 = Symbol(m, 'b2')
        l = List(m, [b1, b2])

        t = split(x=a, axis=0, args=l)
        assert isinstance(next(iter(t)), List)
        m.output(c=t)

    init = dict(a=[[1, 1], [2, 2]])

    c, tape = m.compute(init=init, vout='c', return_tape=True, monitor=print)
    assert_array_equal(c, [[1, 1], [2, 2]])

    vjp = tape.get_vjp()
    init = dict(_c=[[1, 1], [1, 1]])
    _a = vjp.compute(init=init, vout='_a', monitor=print)

    assert_array_equal(_a, [[1, 1], [1, 1]])

    jvp = tape.get_jvp()
    init = dict(a_=[[1, 1], [1, 1]])
    c_ = jvp.compute(init=init, vout='c_', monitor=print)

    assert_array_equal(c_, [[1, 1], [1, 1]])


def test_operator_multi_out():
    @operator
    class op:
        ain = {'x' : '*'}
        # for python 2.x need to use this syntax
        # to preserve orders
        aout = [('y1', '*'),
                ('y2', '*')]

        def apl(self, x):
            return dict(y1=x, y2=2 * x)
        def vjp(self, _y1, _y2):
            return dict(_x = _y1 + 2 * _y2)
        def jvp(self, x_):
            return dict(y1_=x_, y2_=2 * x_)

    with Builder() as m:
        a = m.input('a')
        t1, t2 = op(x=a)
        m.output(c=t1, d=t2)

    init = dict(a=3)

    (c, d), tape = m.compute(init=init, vout=('c', 'd'), return_tape=True)
    assert c == 3
    assert d == 6

    vjp = tape.get_vjp()
    init = dict(_c=1, _d=1)
    _a = vjp.compute(init=init, vout='_a', monitor=print)
    assert _a == 3

    jvp = tape.get_jvp()
    init = dict(a_=1)
    c_, d_ = jvp.compute(init=init, vout=('c_', 'd_'), monitor=print)
    assert c_ == 1
    assert d_ == 2
