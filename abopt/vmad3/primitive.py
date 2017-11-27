import weakref

from .error import InferError, UnpackError, OverwritePrecaution, MissingArgument, BrokenPrimitive
from .symbol import Symbol, Literal

def make_symbol(model, var):
    if isinstance(var, Primitive):
        if len(var.varout) > 1:
            raise UnpackError("More than one output variable, need to unpack them")
        var = next(iter(var.varout.values()))

    if not isinstance(var, Symbol):
        var = Literal(model, var)

    return var

class Primitive(object):
    """ Primitives are building blocks of models.

        Instantiation of a primitive creates a node on a model.

        This is the base class for all operators. Primitive classes are generated
        and attached to the operators classes via the `operator` decorator.

    """

    def _infer_model(self, kwargs):
        kls = type(self)
        model = None

        for argname in kls.ain:
            if not argname in kwargs: raise MissingArgument("input argument '%s' not provided" % argname)

            var = kwargs[argname]

            # unpack the primitive result
            # see __iter__ if explict unpack (a, b = primitive(...))
            # is used.

            if isinstance(var, Primitive):
                var = next(iter(var.varout.values()))

            if isinstance(var, Symbol):
                model = var.model
                self._model = weakref.ref(model)
                return model

        for argname in kls.aout:
            if argname not in kwargs: continue
            var = kwargs[argname]
            if isinstance(var, Symbol):
                model = var.model
                self._model = weakref.ref(model)
                return model

        raise InferError("Cannot infer model from variables -- try to mark at least one literal argument explicitly as Literal")

    def __init__(self, **kwargs):

        kls = type(self)

        # assert the primitive is properly defined.
        for attr in ['ain', 'aout', 'impl', 'func', 'argnames', 'operator']:
            if not hasattr(kls, attr):
                raise BrokenPrimitive("primitive class attribute '%s' is not defined" % attr)

        self.varin = {}
        self.varin_info = {} # currently only the reference id of the symbol
        self.varout = {}
        self.kwargs = {}

        kwargs = kwargs.copy() # will modify

        model = self._infer_model(kwargs)
        self._name = model.unique_name(kls.__name__)

        for argname in kls.ain:
            var = make_symbol(model, kwargs[argname])

            # checking symbol references
            #print(self._name, var.name, id(var), id(model.get(var.name)))

            var.add_reference(self)
            self.varin[argname] = var
            self.varin_info[argname] = len(var.references)

        for argname in kls.aout:
            if not argname in kwargs:
                # if a name is not supplied, generate a name
                varname = self.name + '-' + argname
                var = model.define(varname)
            else:
                var = kwargs[argname]
                # already given a symbol, overwrite it
                # but this doesn't work for gradients
                if len(var.references) != 0:
                    raise OverwritePrecaution("Overwritting used symbols is not supported. Because it breaks vjp.")
                # make a new symbol of the same name
                # var = model.define(var.name)

            self.varout[argname] = var

        # record all 'side' arguments that do not go into derivatives.
        for k, v in kwargs.items():
            if k not in kls.ain and k not in kls.aout:
                self.kwargs[k] = v

        model.append(self)

    def __iter__(self):
        """ for unpacking the results in model building """
        for argname in self.aout:
            yield self.varout[argname]

    @property
    def name(self):
        return self._name

    def __repr__(self):
        return "%s(%s=>%s)" % (self._name, self.varin, self.varout)

    def execute(self, context, tape):
        """ execute the primitive on the context, recording the
            resolved arguments to the tape for replay / gradients.
        """
        resolved_args = []
        resolved = {}
        for argname, var in self.varin.items():
            resolved[argname] = var.resolve(context)

        kwargs = {}
        kwargs.update(resolved)

        # add the extra arguments used by the impl
        for argname in self.argnames:
            if argname not in kwargs:
                kwargs[argname] = self.kwargs[argname]

        tape.append(self, resolved)


        r = type(self).impl(self, **kwargs)

        for argname, var in self.varout.items():
            context[var.name] = r[argname]
