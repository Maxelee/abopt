import numpy

class VM(object):
    @staticmethod
    def inspect(record):
        return str(list((k, "0x%0X" % id(v)) for k, v in record.items()))

    @staticmethod
    def microcode(fout=[], fin=[]):
        """ Declare a subclass member function as a microcode.

            A microcode is a function with names of input and names of output
            It always takes a frontier argument and a list of *args.

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
            func.grad = gradient_decorator
            return func
        # no parameters
        if hasattr(fout, "__call__"):
            return decorator(fout)
        return decorator

    def __init__(self):
        self.microcodes = []

    def push(self, op, *args):
        """ Append to the microcode list of the VM

            Use this to build complicated microcode sequences.

            >>> vm.push('mul', 3.0)
            >>> vm.push('mul', 2.0)
        """
        self.microcodes.append((op, args))

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
        microcodes = self.microcodes

        # must add the final fout into the tape
        # to properly update refcount of the input gradients
        sentinal = [(None, ())]

        for op, args in microcodes + sentinal:
            if op is None:
                impl = lambda self, frontier, *args: None
                impl.fin = fout
                impl.fout = []
            else:
                impl = self._find_impl(op)
            if tape is not None:
                record = {}
                for var in impl.fin:
                    record[var] = frontier[var]
                    if var in impl.fout:
                        # save a copy of the variables for in-place operations.
                        frontier[var] = frontier[var].copy()
                print(op, 'called with', VM.inspect(record))
                tape.append(record)

            impl(self, frontier, *args)

        d = {}
        for name in fout:
            d[name] = frontier[name]
        return d

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

        microcodes = self.microcodes

        # first item in tape is the inital value
        tape = tape[1:]

        refcount = self._refcount(tape)

        # we never use the last record on the tape for the gradient computation
        # we only use the corresponding inputs.
        # but we do need to properly add the refcounts of elements in ginit,
        # such that they are properly cummulated; e.g. some final output variables
        # are irrelevant (we assign 0 to their gradients to speed up computing)

        tape = tape[:-1]

        # holding the gradient of variables
        partial = {}

        frontier = {}
        frontier.update(ginit)
        for (op, args), record in zip(microcodes[::-1], tape[::-1]):
            d = {}
            d.update(record)
            d.update(frontier)
            impl = self._find_impl(op)

            print ('gradient', op, 'before', VM.inspect(record))

#            if any([name not in d for name in impl.g.gin]):
#                print ('gradient', op, 'skipped due to missing', name)
#                continue
            for name in impl.g.gin:
                if name not in d:
                    d[name] = 0

            impl.g(self, d, *args)

            # reduce the result
            for name in impl.g.gout:
                vname = name[1:]
                uid = id(record[vname])
                print('partial gradient', name, d[name])
                if uid not in partial:
                    # this is the first channel, create the gradient storage
                    partial[uid] = d[name]
                else:
                    # this is an additional channel. cummulate the gradient.
                    try:
                        partial[uid][...] += d[name]
                    except:
                        partial[uid] += d[name]
                refcount[uid] = refcount[uid] - 1

                if refcount[uid] == 0:
                    # update the frontier with the new gradients
                    # we no longer need to save it on partial since cummulation is done.
                    frontier[name] = partial.pop(uid)
                    print('finalized gradient', name, frontier[name])
        d = {}
        for name in gout:
            d[name] = frontier[name]
        return d

