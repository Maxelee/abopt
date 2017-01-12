from __future__ import print_function
import numpy
import warnings
import functools

class MicroCode(object):
    """ An object that represents a microcode.

        Mostly a python function with some additional introspection, marking
        the input and output variables.
    """
    def __init__(self, function, ain, aout, literals):
        self.function = function
        self.ain = ain
        self.aout = aout
        self.literals = literals
        self.argnames = function.__code__.co_varnames[1:function.__code__.co_argcount]
        for an in ain:
            if not an in self.argnames:
                raise ValueError(
    "argument `%s` of ain in microcode decorator is not declared by function `%s`"
                       % (an, str(self.function))
                )
        self.gradient = NotImplemented
        functools.update_wrapper(self, function)

    def grad(self, function):
        gout = ['_' + a for a in self.ain]
        gin  = ['_' + a for a in self.aout]

        self.gradient = microcode(gin, gout)(function)
        # allow the gradient with the same name as the original function.
        return self

    def __get__(self, instance, owner):
        """ As a class member, return the microcode,
            As an instance member of VM, returns the function as a method,
            As an instance member of Code, returns a method to add to the code.
        """
        if instance is not None:
            if isinstance(instance, Code):
                @functools.wraps(self.function)
                def method(**kwargs):
                    instance.append(self, kwargs)
                return method
            return self.function.__get__(instance, owner)
        return self

    def __repr__(self):
        return self.function.__name__

    def invoke(self, vm, frontier, kwargs, tape, monitor=None):
        din = {}

        # copy in all arguments
        for an in self.argnames:
            din[an] = kwargs.get(an, an)

        # replace argument with variable name
        # then fetch it from the frontier.
        vin = []
        for an in self.ain + self.literals:
            vn = kwargs.get(an, an)
            din[an] = frontier[vn]
            vin.append(vn)

        if tape is not None:
            tape.append(self, kwargs, din)

        vin = []
        for an in self.argnames:
            data = din[an]
            if an in self.aout and an in self.ain:
                vn = kwargs.get(an, an)
                if vn in din:
                    data = vm.copy(data)
            vin.append(data)

        out = self.function(vm, *vin)

        # zip the output arguments
        if len(self.aout) == 1: out = [out]
        dout = {}
        for an, value in zip(self.aout, out):
            dout[an] = value

        r = {}
        for an in self.aout:
            vn = kwargs.get(an, an)
            r[vn] = dout[an]

        if monitor:
            monitor(self, din, dout, frontier, r)
        return r

def microcode(ain, aout, literals=[]):
    """ Declares a VM member function as a 'microcode'.
        microcode is the building block for Code objects,
        which can be computed and differentiated.

        See MicroCode. 
    """
    def decorator(func):
        return MicroCode(func, ain, aout, literals)
    return decorator

class VM(object):
    """ A virtual machine that interprets and runs Code objects
        consisting of microcodes.

        Subclass VM to add more microcodes.
        Override `copy` and `add` to support different types of
        variables.

        Convention for gradient is to prepend `_`, e.g. `_x` is the gradient
        backtraced to `x`.

        The Each microcode carries a list of input and output arguments (
        `ain` and `aout`) that can be assigned as variable names (string).

        The rest of arguments in the function signature
        are external parameters who do not go into gradients.

        Example
        -------

        >>> vm = VM()
        >>> code = vm.code()
        >>> code.add(a='x', b='x', c='y')
        >>> code.compute('y', {'x' : 10})

    """

    @microcode(ain=['a'], aout=['b'])
    def copy(self, a): return 1.0 * a

    @copy.grad
    def gcopy(self, _b): return _b

    @microcode(ain=['a', 'b'], aout=['c'])
    def add(self, a, b):
        if a is VM.Zero: return b
        if b is VM.Zero: return a
        return a + b

    @add.grad
    def gadd(self, _c, _a, _b): return _c, _c

    def code(self):
        """ Creates a Code object for this VM.

            Build model with this.
        """
        d = {}
        for name, method in type(self).__dict__.items():
            if isinstance(method, MicroCode):
                d[name] = method
        MyCode = type("Code%s" % (type(self).__name__), (Code, ), d)
        return MyCode(self)

    def gradient(self, tape, add=None):
        """ Create a code object that backtraces the gradient of a previously
            recorded execution in `tape`.

            The `add` microcode (None means `type(self).add`) reduces partial
            derivatives.

        """
        newinst = self.code()

        if add is None:
            add = type(self).add

        occurances = {}

        def emit_add(a, b, c):
            din = {}
            din[add.ain[0]] = a
            din[add.ain[1]] = b
            din[add.aout[0]] = c
            newinst.append(add, din)

        for microcode, kwargs, record in tape[::-1]:
            din = {}

            din.update(kwargs)
            din.update(record)

            # inputs
            for an in microcode.aout:
                din['_' + an] = '_' + kwargs.get(an, an)

            for an in microcode.ain:
                # need to rename to avoid accidentally overwrite
                # a finished gradient
                din['_' + an] = '#partial#_' + kwargs.get(an, an)
                value = record[an]
                if tape.get_refcount(value) == 1:
                    # direct overwriting is OK. no partials.
                    din['_' + an] = '_' + kwargs.get(an, an)
                else:
                    if an in microcode.aout:
                        # rename the input.
                        emit_add("", '_' + kwargs.get(an, an), din['_' + an])

            newinst.append(microcode.gradient, din)

            # outputs
            for an in microcode.ain:
                value = record[an]
                uid = tape.get_uid(value)
                oc = occurances.get(uid, 0)
                occurances[uid] = oc + 1

                if tape.get_refcount(value) > 1:
                    reduceto = '_' + kwargs.get(an, an)
                    partial = din['_' + an]
                    if oc > 0:
                        emit_add(reduceto, partial, reduceto)
                    else:
                        # move the partial to reduceto
                        # OK to use a move because a partial is only used once.
                        emit_add("", partial, reduceto)
                else:
                    # result already in right place
                    pass

        return newinst

    @microcode(ain=['x'], aout=['y'])
    def func(self, x, factor):
        """ this is a function """
        y = factor * x
        return y

    @func.grad
    def gfunc(self, x, factor, _y):
        _x = factor * _y
        return _x

class Tape(list):
    """ A tape records the computation of a code object.
        The tape object can then be used by the VM to build
        a gradient code object.
    """
    def __init__(self):
        list.__init__(self)
        self.init = {}
        self._refcount = {}

    def __str__(self):
        def format(microcode, kwargs, d):
            r = str(microcode)
            r += ' '
            r += str(kwargs)
            r += ' '
            r += ', '.join([ '%s(%08X) : %s ' % (name, id(value), str(value)[:17])
                    for name, value in d.items()])
            return r
        r = '-- Inputs (%08X)----\n' % id(self)
        r += '\n'.join([format(microcode, kwargs, d) for microcode, kwargs, d in self ])
        r += '\n'
        r += '-- Refcounts ----\n'
        r += ' '.join(["%08X : %d" % refcount for refcount in self._refcount.items()])
        return r

    def get_uid(self, value):
        return id(value)

    def get_refcount(self, value):
        uid = id(value)
        return self._refcount.get(uid, 0)

    def append(self, microcode, kwargs, din):
        """ add a record to the tape. Record is the argument name and the value. """
        for an, value in din.items():
            uid = id(value)
            self._refcount[uid] = self._refcount.get(uid, 0) + 1
        list.append(self, (microcode, kwargs, din))

class Code(list):
    """ A code object is a sequence of microcodes with input, output variables and parameters.
    """
    def __init__(self, vm):
        self.microcodes = []
        self.vm = vm

    def append(self, microcode, kwargs):
        self.microcodes.append( (microcode, kwargs))

    def __repr__(self):
        r = "--Code---\n"
        def format(code, kwargs):
            return '%s : %s' % (str(code), str(kwargs))

        r += '\n'.join(format(code, kwargs) for code, kwargs in self.microcodes)
        r += '\n'
        return r

    def _find_inputs(self):
        live = set()
        for microcode, kwargs in reversed(self.microcodes):
            for an in microcode.aout:
                vn = kwargs.get(an, an)
                if vn in live:
                    live.remove(vn)

            for an in microcode.ain:
                vn = kwargs.get(an, an)
                live.add(vn)
        return list(live)

    def compute(self, vout, init, tape=None, monitor=None):
        if not isinstance(vout, (tuple, list)):
            vout = [vout]
            squeeze = True
        else:
            squeeze = False

        inputs = self._find_inputs()
        frontier = {}
        frontier.update(init)
        frontier[""] = VM.Zero

        for vn in inputs:
            if vn not in frontier:
                raise ValueError("`%s` not defined in inputs" % vn)

        if tape is not None:
            tape.init.update(init)

        started = False
        for i, (microcode, kwargs) in enumerate(self.microcodes):
            try:
                r = microcode.invoke(self.vm, frontier, kwargs, tape, monitor)
            except Exception as e:
                print("Failure in running `%s`" % microcode)
                raise
            frontier.update(r)
            future = self.microcodes[i+1:]
            self._gc(frontier, future, vout, monitor)
            if self._terminate(future, vout):
                break

        r = [frontier[vn] for vn in vout]
        if squeeze:
            r = r[0]
        return r


    def _gc(self, frontier, future, vout, monitor=None):
        """ remove variables that are never used again """
        used = []
        used.extend(vout)
        for microcode, kwargs in future:
            for an in microcode.ain + microcode.literals:
                vn = kwargs.get(an, an)
                used.append(vn)

        used = set(used)
        for vn in list(frontier.keys()):
            if vn not in used:
                if monitor:
                    monitor("freeing", vn)
                frontier.pop(vn)

    def _terminate(self, future, vout):
        """ No variables in vout are mentioned in the future, we can terminate. """
        used = []
        for microcode, kwargs in future:
            for an in microcode.aout:
                vn = kwargs.get(an, an)
                used.append(vn)

        used = set(used)
        for vn in vout:
            if vn in used: return False
        return True




#####################
#
# ZeroType.
#
# Zero * anything = Zero; Zero + anything = anything
#
# VM.Zero is used to suppress gradient computation
# backtracing from VM.Zero shall always give VM.Zero
# regardless of the microcode function; this may 
# get more complicated if a microcode function
# has multiple outputs -- e.g. if the backtrace gradient
# of some are not VM.Zero.
#
# In case it occurs in a regular Python expression,
# these operator overides ensure we can 
# propagate VM.Zero properly.
#
# In other cases the microcode functions may need
# to special case on variables that are VM.Zero.

def ZeroType():
    """ creates a special type of ZeroType; """
    def self(self, *args): return self
    def other(self, other): return other
    def zde(self, a): raise ZeroDivisionError
    def __sub__(self, a): return -a
    def __xor__(self, a): return ~a
    def __int__(self): return 0
    def __float__(self): return 0.0
    def __round__(self): return 0
    def __array__(self): return numpy.array(0)
    def __repr__(self): return "<ZERO>"
    dict = {}
    for name, value in locals().items():
         if name.startswith("__"): dict[name] = value

    for name in [
        "neg", "pos", "abs", "invert", "complex",
        "mul", "rmul", "matmul", "rmatmul", 
        "mod", "divmod", "div", "truediv", "floordiv",
        "pow",
        "and", "rand", "lshift", "rlshift", "rshift", "rrshift",
        "getitem", "reversed"]:
        dict["__" + name + "__"] = self

    for name in [
        "rmod", "rdivmod", "rdiv", "rtruediv", "rfloordiv",
        "rpow", "rsub", "rxor"]:
        dict["__" + name + "__"] = zde

    for name in [
        "add", "radd", "or", "ror"]:
        dict["__" + name + "__"] = other

    dict["__repr__"] = __repr__
    return type("ZeroType", (object,), dict)

ZeroType = ZeroType()
Zero = ZeroType()

VM.Zero = Zero
VM.microcode = staticmethod(microcode)

