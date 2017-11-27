from .symbol import Symbol, Literal
from .operator import terminal
from .error import ModelError

class Model(list):
    def __init__(self):
        self._counter = 0
        self._vin = []
        self._vout = []
        self._syms = {}

    def define(self, varname):
        r = Symbol(self, varname)
        self._syms[varname] = r
        return r

    def get(self, varname):
        return self._syms[varname]

    def has(self, varname):
        return varname in self._syms

    def input(self, *args):
        r = [self.define(a) for a in args]
        self._vin.extend(r)
        return r

    def output(self, **kwargs):
        for varname, oldvar in kwargs.items():
            for var in self._vout:
                if var.name == varname:
                    raise ModelError("Variable %s is already marked as an output" % varname)

            var = self.define(varname)
            terminal.opr(x=oldvar, y=var)
            self._vout.append(var)

    def compile(self): pass

    def unique_name(self, str):
        self._counter += 1
        return '%s@%d' % (str, self._counter)

    def __repr__(self):
        return "Model: %s => %s" % (self._vin, self._vout)

class ModelBuilder(Model):
    def __enter__(self): return self
    def __exit__(self, *args): self.compile()
