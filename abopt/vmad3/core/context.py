from .operator import terminal
from .error import UnexpectedOutput
from .tape import Tape

class Context(dict):
    """ A context is a collection of python objects referred by symbol names;

        This is where the execution of a model occurs.
    """
    def __init__(self, **kwargs):
        self.update(kwargs)

    def remove_unused(self, nodes):
        """ remove objects not used by nodes"""
        used = set()
        for p in nodes:
            for argname, ref in p.varin.items():
                used = used.union(ref.get_symbol_names())

        toremove = []
        for key in self:
            if not key in used:
                toremove.append(key)

        for key in toremove:
            self.pop(key)

    def result_used(self, node):
        # FIXME: this doesn't remove all of the unused
        # may need to fix this in 'compile' or 'optimize'.
        if isinstance(node, terminal._apl):
            return True
        for argname, var in node.varout.items():
            if var.has_reference(): return True
        return False

    def compute(self, model, vout, return_tape=False, monitor=None):
        """
            compute a model in the current context (self).

        """
        tape = Tape(model)

        if isinstance(vout, str):
            single_return = True
            vout = [vout]
        else:
            single_return = False

        _voutnames = set([var.name for var in model._vout])

        for varname in vout:
            if varname not in _voutnames:
                raise UnexpectedOutput("Requested vout %s is not defined by the model as an output" % varname)

        r = {}
        for i, node in enumerate(model):

            if self.result_used(node):
                self.execute(node, tape)

            if isinstance(node, terminal._apl):
                for argname, var in node.varout.items():
                    r[var.name] = self[var.name]

            self.remove_unused(model[i+1:])

            if monitor is not None:
                monitor(node, self)

        r = [r[varname] for varname in vout]

        if single_return:
            r = r[0]

        if return_tape:
            r = r, tape

        return r

    def execute(self, node, tape):
        """ execute a node on the context, recording the
            resolved arguments to the tape for replay / gradients.
        """

        resolved = {}
        for argname, ref in node.varin.items():
            var = ref.symbol
            resolved[argname] = var.resolve(self)

        kwargs = {}
        kwargs.update(resolved)

        # add the extra arguments used by the impl
        for argname in node.argnames:
            if argname not in kwargs:
                kwargs[argname] = node.kwargs[argname]

        tape.append(node, resolved)

        r = node.call(**kwargs)

        for argname, var in node.varout.items():
            var.store(self, r[argname])

