import numpy
import warnings
class ZeroType(object):
    # this is similiar but not exactly the Bottom type.
    # https://en.wikipedia.org/wiki/Bottom_type
    #
    # It is a special kind of Zero
    # any multiplication computation path involves Zero shall give Zero
    # any additive computation path involves Zero shall gives the other operand.

    def __init__(self):
        pass
    def __array__(self):
        return numpy.array(0)
    def __neg__(self):
        return self
    def __pos__(self):
        return self
    def __abs__(self):
        return self
    def __invert__(self):
        return self
    def __complex__(self):
        return self
    def __int__(self):
        return 0
    def __float__(self):
        return 0.0
    def __round__(self):
        return 0
    def __mul__(self, a):
        return self
    def __rmul__(self, a):
        return self
    def __matmul__(self, a):
        return self
    def __rmatmul__(self, a):
        return self
    def __add__(self, a):
        return a
    def __radd__(self, a):
        return a
    def __sub__(self, a):
        return -a
    def __rsub__(self, a):
        return a
    def __mod__(self, a):
        return self
    def __rmod__(self, a):
        return self
    def __divmod__(self, a):
        return self
    def __rdivmod__(self, a):
        raise ZeroDivisionError
    def __div__(self, a):
        return self
    def __rdiv__(self, a):
        raise ZeroDivisionError
    def __truediv__(self, a):
        return self
    def __rtruediv__(self, a):
        raise ZeroDivisionError
    def __floordiv__(self, a):
        return self
    def __rfloordiv__(self, a):
        raise ZeroDivisionError
    def __pow__(self, a, modulo):
        return self
    def __rpow__(self, a):
        # really should be a different error
        # we never raise something to a gradient power
        return ZeroDivisionError
    def __and__(self, a):
        return self
    def __rand__(self, a):
        return self
    def __xor__(self, a):
        return ~a
    def __rxor__(self, a):
        return ~a
    def __or__(self, a):
        return a
    def __ror__(self, a):
        return a
    def __lshift__(self, a):
        return self
    def __rlshift__(self, a):
        return self
    def __rshift__(self, a):
        return self
    def __rrshift__(self, a):
        return self
    def __getitem__(self, key):
        return self
    def __reversed__(self, key):
        return self

class VM(object):
    Zero = ZeroType()

    @staticmethod
    def inspect(record):
        return str(list((k, "0x%0X" % id(v)) for k, v in record.items()))

    @staticmethod
    def microcode(fout=[], fin=[], lout=[]):
        """ Declare a subclass member function as a microcode.

            A microcode is a function with names of input and names of output
            It always takes a frontier argument and a list of *args.

            lout is the list of 'literal' outputs (do not participate in gradients)

            >>> @VM.microcode(fin=['x'], fout=['x'])
            >>> def mul(self, frontier, factor):
            >>>    frontier['x'] = factor * frontier['x']

            The backtrace gradient microcode shall be
            >>> @mul.grad
            >>> @VM.microcode
            >>> def gmul(self, frontier, factor):
            >>>    frontier['^x'] = factor * frontier['^x']

            Notice that `^` denotes the backtraced gradient against a variable.
            The same name can be both lvalue and rvalue
        """
        def decorator(func):
            def gradient_decorator(func1):
                func1.gout = ['^' + v for v in fin]
                func1.gin  = ['^' + v for v in fout]
                func.g = func1
                return func1

            func.fout = fout
            func.fin = fin
            func.lout = lout
            func.grad = gradient_decorator
            return func
        # no parameters
        if hasattr(fout, "__call__"):
            return decorator(fout)
        return decorator

    def __init__(self):
        self._microcodes = []

    @property
    def microcodes(self):
        r = self._microcodes + [(None, ())]
        return r

    def push(self, op, *args):
        """ Append to the microcode list of the VM

            Use this to build complicated microcode sequences.

            >>> vm.push('mul', 3.0)
            >>> vm.push('mul', 2.0)
        """
        impl = self._find_impl(op)
        self._microcodes.append((impl, args))

    def _find_impl(self, op):
        for name, impl in self.__class__.__dict__.items():
            if name == op: return impl
        raise AttributeError("code %s is not found" % op)

    def compute(self, fout, init, tape=None):
        """
            Run the list of microcodes with `init` dictionary as input
            Record the results on `tape` (list), and return a dictionary
            contains variables named in fout (list).
            The items in the init shall support [...] or the '+' operator

            >>> vm.compute(['x'], {'x': numpy.ones(10)})

        """

        frontier = {}
        frontier.update(init)
        literals = []

        for impl, args in self.microcodes:
            if impl is None:
                # sentinal,
                # add the final fout into the tape
                # to properly update refcount of the input gradients

                impl = lambda self, frontier: None
                impl.fin = fout
                impl.fout = []
                impl.lout = []

            if tape is not None:
                record = {}
                for var in impl.fin + literals:
                    record[var] = frontier[var]
                    if var in impl.fout:
                        # save a copy of the variables for in-place operations.
                        # the upstream is not necessary an array, so we 
                        if hasattr(frontier[var], 'copy'):
                            frontier[var] = frontier[var].copy()
                        else:
                            # if it can't clone itself, we ask for help from numpy.
                            frontier[var] = numpy.array(frontier[var], copy=True)

                # print(op, 'called with', VM.inspect(record))
                tape.append(record)

            literals = list(set(literals + impl.lout))
            impl(self, frontier, *args)

        if tape is not None:
            # record fout literals
            # for future gradient
            tape.append(fout)
            tape.append(literals)

        r = {}
        for name in fout:
            r[name] = frontier[name]
        return r

    @staticmethod
    def _refcount(tape):
        """ count number of references to any variables on a tape """
        d = {}
        for record in tape:
            for name, value in record.items():
                uid = id(value)
                d[uid] = d.get(uid, 0) + 1
        return d

    def gradient(self, gout, ginit, tape):
        """ Backtrace the gradient from ginit (dict).

            tape is obtained from a prevoius call to `compute`.

            Returns a dict contains the requested gradients in gout (list).

            >>> tape = []
            >>> vm.compute(['x'], {'x': numpy.ones(10)})
            >>> vm.gradient(['^x'], {'^x', numpy.ones(10)}, tape)
        """

        sentinal = [(None, ())]

        fout = tape[-2]
        literals = tape[-1]

        refcount = self._refcount(tape[:-2])

        #for i, n in refcount.items():
        #    print ('0X%X' %i, n)

        # we never use the last record on the tape for the gradient computation
        # we only use the corresponding inputs.
        # but we do need to properly add the refcounts of elements in ginit,
        # such that they are properly cummulated; e.g. some final output variables
        # are irrelevant (we assign VM.Zero to their gradients to speed up computing)

        # holding the gradient of variables
        partial = {}

        frontier = {}
        for (impl, args), record in reversed(zip(self.microcodes, tape)):
        #    print ('gradient', impl.__name__, 'before', VM.inspect(record))

            d = {}
            d.update(record)
            d.update(frontier)

            if impl is None:
                # sentinal -- initialization
                # pump up d with the initial and be aware of missing items
                # in ginit -- if they are in gin we later set them to zero.

                impl = lambda : None
                impl.g = lambda self, d: None
                # literals are skipped from gradients, even if they are
                # requested by fout.
                impl.g.gin = ['^' + v for v in fout if v not in literals]
                impl.g.gout = ['^' + v for v in fout if v not in literals]
                d.update(ginit)
            
            for name in impl.g.gin:
                # non existing inputs are implied to start with gradients of VM.Zero
                if name not in d:
                    d[name] = VM.Zero

            impl.g(self, d, *args)

            # reduce the result
            for name in impl.g.gout:
                vname = name[1:]
                uid = id(record[vname])
                #print('partial gradient', name, refcount[uid], d[name])
                pg = d[name]
                if uid not in partial or partial[uid] is VM.Zero:
                    # this is the first channel, create the gradient storage
                    partial[uid] = pg
                elif pg is not VM.Zero:
                    # this is an additional channel. cummulate the gradient.
                    partial[uid][...] += pg
                refcount[uid] = refcount[uid] - 1

                if refcount[uid] == 0:
                    # update the frontier with the new gradients
                    # we no longer need to save it on partial since cummulation is done.
                    frontier[name] = partial.pop(uid)
                #    print('finalized gradient', name, frontier[name])

        for i, v in partial.items():
            warnings.warn('problem: remainging partial : 0X%X %d %s' % (i, refcount[i], str(v)), RuntimeWarning)

        r = {}
        for name in gout:
            r[name] = frontier[name]
        return r

