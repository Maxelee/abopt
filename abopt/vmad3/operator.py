"""
    Routines to define an operator

    use @operator decorator on a class to define an operator.

    Example: see the source code of :class:`add`

    use @nested.nestedoperator to define a nested operator, where
    you only need to define a model and the ain, aout

"""
class Operator(object): pass

def operator(kls):
    """ Decorator to declare an operator. 

        The decorator is similar to a meta-class. It produces a
        new class with Operator as a baseclass, and opr, jvp and vjp are
        converted to primitives.

        An operator must define `ain, aout` and opr, vjp, jvp functions.

        ain : dict(name => type_pattern) describes the input arguments of
              the operator
        aout : dict(name => type_pattern) describes the output arguments of
              the operator

        Currently the type_pattern is not used; the plan is to add multi-dispatch
        if it is proven to be useful.

        opr : function(self, ...) the operator itself; shall return a dictionary
              of the evaluated values (exactly the same number of aout).
              all input arguments are resolved to python objects;
              it can have extra arguments in addition to ain.

        jvp : function(self, ...) the jacobian vector product. The convention
              is to use '_' + argname as the name of vectors. used for back-prop.

        vjp : function(self, ...) the vector jacobian product. The convention
              is to use argname + '_' as the name of vectors. used for foward-prop.

    """

    kls.opr = _make_primitive(kls, 'opr', kls.opr)
    kls.vjp = _make_primitive(kls, 'vjp', kls.vjp)
    kls.jvp = _make_primitive(kls, 'jvp', kls.jvp)

    return type(kls.__name__, (Operator, kls, kls.opr), {})

def _make_primitive(operator, func, impl, argnames=None):
    """ create primitives for the operator.

        This is used to define a primitive based on the unbound method
        defined in the operator class.

    """
    from .primitive import Primitive

    assert func in ('opr', 'vjp', 'jvp')

    kls = operator

    aout = {}
    ain = {}
    if argnames is None:
        argnames = impl.__code__.co_varnames[1:impl.__code__.co_argcount]

    if func == 'opr':
        ain = kls.ain
        aout = kls.aout
    elif func == 'vjp' : # in and out are prefixed.
        for arg in argnames:
            if arg in kls.ain: # useful original arguments
                ain[arg] = kls.ain[arg]

        for arg in kls.ain:
            aout['_' + arg] = kls.ain[arg]

        for arg in kls.aout:
            ain['_' + arg] = kls.aout[arg]

    elif func == 'jvp' : # in and out are prefixed.
        for arg in argnames:
            if arg in kls.ain: # useful original arguments
                ain[arg] = kls.ain[arg]

        for arg in kls.ain:
            ain[arg + '_'] = kls.ain[arg]

        for arg in kls.aout:
            aout[arg + '_'] = kls.aout[arg]

    bases = (Primitive,)

    primitive = type(operator.__name__ + '-' + func,
            bases,
            dict(
                impl     = impl,
                func     = func,
                ain      = ain,
                aout     = aout,
                argnames = argnames,
                operator = operator,
            ))
    return primitive


# special operator used for partial gradient summation
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

# special operator used for check-gradients
@operator
class to_scalar:
    ain  = {'x': 'ndarray'}
    aout = {'y': '*'}

    def opr(self, x,  y):
        return dict(y = (x**2).sum())

    def vjp(self, _x, _y):
        return dict(_x = 2. * _y)

    def jvp(self, x_, y_):
        return dict(y_ = 2. * x_)

# special operator for marking an output
@operator
class terminal:
    ain  = {'x': '*'}
    aout = {'y': '*'}

    def opr(self, x):
        return dict(y=x)
    def vjp(self, _y):
        return dict(_x=_y)
    def jvp(self, x_):
        return dict(y_=x_)

