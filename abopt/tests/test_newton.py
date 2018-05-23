from __future__ import print_function
import numpy

from abopt.abopt2 import Problem, Preconditioner
from abopt.newton import Newton

from numpy.testing import assert_allclose
from abopt.testing import RosenProblem

import pytest

def test_newton():
    nt = Newton()

    problem = RosenProblem()

    problem.atol = 1e-7 # ymin = 0

    x0 = numpy.zeros(20)
    r = nt.minimize(problem, x0, monitor=print)
    assert_allclose(r.x, 1.0, rtol=1e-4)
    assert r.converged

def test_newton_pre():
    nt = Newton()

    def diag_scaling(v, direction):
        if direction == -1:
            return 0.05 * v
        else:
            return 20 * v

    precond = Preconditioner(Pvp=diag_scaling, vPp=diag_scaling)
    problem = RosenProblem(precond=precond)

    problem.atol = 1e-7 # ymin = 0

    x0 = numpy.zeros(20)
    r = nt.minimize(problem, x0, monitor=print)
    assert_allclose(r.x, 1.0, rtol=1e-4)
    assert r.converged
