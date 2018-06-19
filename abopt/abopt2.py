from .vectorspace import VectorSpace
from .vectorspace import real_vector_space
from .vectorspace import complex_vector_space

from .lbfgs import LBFGS
from .naivemethods import GradientDescent, DirectNewton
from .trustregion import TrustRegionCG

# compatibility
from .base import State
from .base import Preconditioner
from .base import Problem


def minimize(optimizer, objective, gradient, x0, hessian_vector_product=None,
    monitor=None, vs=real_vector_space, precond=None):

    problem = Problem(objective, gradient, hessian_vector_product=hessian_vector_product, vs=vs, precond=precond)

    return optimizer.minimize(problem, x0, monitor=monitor)
