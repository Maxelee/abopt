from abopt.vmad3 import Builder
from numpy.testing import assert_array_equal, assert_allclose

class BaseScalarTest:
    """ Basic correctness of gradient against numerical with to_scalar """

    to_scalar = None # operator for norm-2 scalar

    import numpy
    x = numpy.arange(10)  # free variable x
    x_ = numpy.eye(10)    # a list of directions of x_ to check for directional gradients.

    y = sum(x ** 2)       # expected output variable y, scalar
    epsilon = 1e-3

    def model(self, x):
        return x          # override and build the model will be converted to a scalar later.

    def setup(self):
        with Builder() as m:
            x = m.input('x')
            x = self.model(x)
            y = self.to_scalar(x)
            m.output(y=y)

        self.m = m

        y_ = []
        for x_ in self.x_:
            # run a step along x_
            xl = self.x - x_ * (self.epsilon * 0.5)
            xr = self.x + x_ * (self.epsilon * 0.5)

            # numerical
            yl = self.m.compute(init=dict(x=xl), vout='y', return_tape=False)
            yr = self.m.compute(init=dict(x=xr), vout='y', return_tape=False)

            y_.append((yr - yl) / self.epsilon)

        y, tape = self.m.compute(init=dict(x=self.x), vout='y', return_tape=True)
        self.tape = tape
        self.y_ = y_
        import numpy

        if numpy.allclose(y_, 0):
            raise AssertionError("The test case is not powerful enough, since all derivatives at this point are zeros")

    def test_opr(self):
        init = dict(x=self.x)
        y1 = self.m.compute(vout='y', init=init, return_tape=False)
        # correctness
        assert_allclose(y1, self.y)

    def test_jvp_finite(self):
        jvp = self.tape.get_jvp()

        for x_, y_ in zip(self.x_, self.y_):
            init = dict(x_=x_)
            y_1 = jvp.compute(init=init, vout='y_', return_tape=False)

            assert_allclose(y_1, y_)

    def test_vjp_finite(self):
        import numpy
        vjp = self.tape.get_vjp()

        init = dict(_y=1.0)
        _x = vjp.compute(init=init, vout='_x', return_tape=False)

        for x_, y_ in zip(self.x_, self.y_):
            assert_allclose(numpy.sum(_x * x_), y_)

