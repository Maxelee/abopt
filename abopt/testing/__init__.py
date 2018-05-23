from abopt.abopt2 import Problem, Preconditioner
from scipy.optimize import rosen, rosen_der, rosen_hess_prod
import numpy

class ChiSquareProblem(Problem):
    """
        chisquare problem with

        y = |J phi(x) - 1.0|^2
    """
    def __init__(self, J, phi=lambda x:x, phiprime=lambda x: 1, precond=None):
        def f(x): return J.dot(phi(x))
        def vjp(x, v): return v.dot(J) * phiprime(x)
        def jvp(x, v): return J.dot(v * phiprime(x))

        def objective(x):
            y = f(x)
            return numpy.sum((y - 1.0) ** 2)

        def gradient(x):
            y = f(x)
            return vjp(x, y - 1.0) * 2

        def hessian(x, v):
            v = numpy.array(v)
            return vjp(x, jvp(x, v)) * 2

        Problem.__init__(self, objective=objective,
                      gradient=gradient,
                      hessian_vector_product=hessian, precond=precond)

class RosenProblem(Problem):
    def __init__(self, precond=None):
        Problem.__init__(self, objective=rosen, gradient=rosen_der,
                    hessian_vector_product=rosen_hess_prod, precond=precond)
