from __future__ import print_function
import warnings
import functools
import logging

logger = logging.getLogger("VMAD")
_logging_handler = logging.StreamHandler()
logger.addHandler(_logging_handler)

class LValue(object):
    def __init__(self, name, ns):
        self.ns = ns
        self.name = name

    def __getattr__(self, attr): return getattr(self[...], attr)
    def __repr__(self): return "LValue:%s" % self.name
    def __getitem__(self, index): return self.ns[self.name]
    def __setitem__(self, index, value): self.ns[self.name] = value

class Instruction(object):
    def __init__(self, body, ain, aout):
        self.body = body
        self.ain = ain
        self.aout = aout
        self.argnames = body.__code__.co_varnames[1:body.__code__.co_argcount]
        for an in ain:
            if not an in self.argnames:
                raise ValueError(
    "argument `%s` of ain in microcode decorator is not declared by function `%s`"
                       % (an, str(self.body))
                )
        functools.update_wrapper(self, body)

    def __repr__(self):
        return self.body.__name__

    def create_node(self, engine, kwargs):
        nodetype = type(self).NodeType
        node = nodetype(engine, self, kwargs)
        return node

class Variable(object):
    def __init__(self, name, version):
        self.name = name
        self.version = version

    def __hash__(self): return hash(self.name + '-%s' % self.version)
    def __eq__(self, other): return self.name == other.name and self.version == other.version

    def __repr__(self):
        if self.version is not None:
            return "%s/%d" % (self.name, self.version)
        else:
            return "%s" % (self.name)

class Argument(object):
    def __init__(self, name, value):
        self.name = name
        self.value = value

    def __repr__(self):
        return "%s:%s=%s" % (type(self).__name__, self.name, self.value)

class IArgument(Argument):
    pass
class OArgument(Argument):
    pass
class IOArgument(Argument):
    pass
class EXArgument(Argument):
    pass

class Node(object):
    def __init__(self, engine, instr, kwargs):
        self.instr = instr
        self.engine = engine
        self.args = []
        kwargs = kwargs.copy()
        for arg in instr.argnames:
            if arg in instr.ain:
                if arg in instr.aout:
                    var = IOArgument(arg, kwargs.pop(arg, arg))
                else:
                    var = IArgument(arg, kwargs.pop(arg, arg))
            elif arg in instr.aout:
                var = OArgument(arg, kwargs.pop(arg, arg))
            else:
                var = EXArgument(arg, kwargs.pop(arg))
            self.args.append(var)
        if len(kwargs) > 0:
            raise ValueError("additional kwargs are found: %s" % list(kwargs.keys()))

    def bind(self, frontier, results):
        """ bind args to objects in frontier, or LValues """
        bound = []
        instr = self.instr
        for arg in self.args:
            if isinstance(arg, (IArgument, IOArgument)):
                bound.append(frontier[arg.value.name])
            elif isinstance(arg, OArgument):
                bound.append(LValue(arg.value.name, results))
            else:
                bound.append(arg.value)
        return bound

    def __repr__(self):
        return "%s(%s)" % (self.instr, self.args)

class Primitive(Instruction):
    def __init__(self, body, ain, aout):
        Instruction.__init__(self, body, ain, aout)
        self.vjp = NotImplemented

    def defvjp(self, body):
        """ Define the back-propagation gradient operator. """
        gout = ['_' + a for a in self.ain]
        gin  = ['_' + a for a in self.aout]

        body.__name__ = "G:" + self.body.__name__
        self.vjp = Primitive(body, gin, gout)
        # allow the gradient with the same name as the original body.
        return self.vjp

    class NodeType(Node):
        def __init__(self, engine, instr, kwargs):
            Node.__init__(self, engine, instr, kwargs)

        def copy(self):
            node = NodeType(engine, instr, kwargs)
            return node

        def invoke(self, frontier):
            logger.info("%s invoked" % (self))
            out = {}
            bound = self.bind(frontier, out)
            self.instr.body(self.engine, *bound)
            return out

def primitive(ain, aout): return lambda body: Primitive(body, ain, aout)

class Programme(Instruction):
    def __init__(self, body, ain, aout):
        Instruction.__init__(self, body, ain, aout)

    class NodeType(Node):
        def __init__(self, engine, instr, kwargs):
            Node.__init__(self, engine, instr, kwargs)
            codeseg = CodeSegment(engine)
            self.instr.body(codeseg, *[arg.value for arg in self.args])
            self.codeseg = codeseg

        def copy(self):
            node = NodeType(engine, instr, kwargs)
            node.codeseg = codeseg
            return node

        def invoke(self, frontier):
            logger.info("%s invoked" % self)
            vout = [ arg.value.name for arg in self.args
                    if isinstance(arg, (OArgument, IOArgument))]
            out = self.codeseg.compute(vout, frontier)

            return dict(zip(vout, out))

def programme(ain, aout): return lambda body: Programme(body, ain, aout)

class Tape(object):
    def __init__(self, init):
        self.records = []
        self.init = {}
        self.init.update(init)

    def append(self, node, frontier):
        d = {}
        for arg in node.args:
            if isinstance(arg, (IArgument, IOArgument)):
                d[arg.value.name] = (arg.value.version, frontier[arg.value.name])

        self.records.append((node, d))

    def __repr__(self):
        return '\n'.join('%s | %s' % (node, list(d.keys())) for node, d in self.records)

class Engine(object):
    pass

class CodeSegment(object):
    def __init__(self, engine):
        self.engine = engine
        self.nodes = []
        self.defaults = {} # use these if not provided in init

        self.liveset = {} # stores the version of variable with the same name
                          # each overwrite will increase this number
        self.refs = {} # stores the numbers a versioned Variable used as input

    def copy(self):
        code = CodeSegment(self.engine)
        code.nodes.extend(self.nodes)
        code.defaults.update(self.defaults)
        code.liveset.update(self.liveset)
        code.refs.update(self.refs)

    def _get_version(self, var):
        return self.liveset.get(var, 0)

    def _inc_version(self, var):
        version = self._get_version(var) + 1
        self.liveset[var] = version
        return version

    def _get_ref(self, var):
        return self.refs.get(var, 0)

    def _inc_ref(self, var):
        ref = self._get_ref(var) + 1
        self.refs[var] = ref
        return ref

    def append(self, node):
        for arg in node.args:
            version = self._get_version(arg.value)
            if isinstance(arg, IArgument):
                arg.value = Variable(arg.value, version)
                self._inc_ref(arg.value)
            elif isinstance(arg, IOArgument):
                arg.value = Variable(arg.value, version)
                self._inc_ref(arg.value)
                # see the old version, writes the new version.
                version = self._inc_version(arg.value)
            elif isinstance(arg, OArgument):
                version = self._inc_version(arg.value)
                arg.value = Variable(arg.value, version)

        self.nodes.append(node)

    def _build_free_list(self):
        ocd = {}
        free_list = []
        for node in self.nodes:
            item = []
            for arg in node.args:
                version = self._get_version(arg.value)
                if isinstance(arg, (IArgument, IOArgument)):
                    ocd[arg.value] = ocd.get(arg.value, 0) + 1
                    if ocd[arg.value] == self._get_ref(arg.value):
                        item.append(arg.value)
            free_list.append(item)
        return free_list

    def __getattr__(self, name):
        try:
            item = getattr(self.engine, name)
        except AttributeError:
            raise AttributeError("%s is not a declared instruction in %s" % (name, type(self.engine)))

        if isinstance(item, Instruction):
            instr = item
            def func(**kwargs):
                self.append(instr.create_node(self.engine, kwargs))
            return func
        else:
            raise TypeError

    def compute(self, vout, init, return_tape=False):
        if hasattr(self.engine, "Copy"):
            copy = self.engine.Copy.body
        else:
            copy = lambda x: x * 1.0

        if not isinstance(vout, (tuple, list, set)):
            vout = [vout]
            squeeze = True
        else:
            squeeze = False

        frontier = {}
        free_list = self._build_free_list()

        for var, value in self.defaults.items():
            frontier[var] = value
        for var, value in init.items():
            frontier[var] = value

        if return_tape:
            tape = Tape(frontier)
        else:
            tape = None

        for i, (node, abandon) in enumerate(zip(self.nodes, free_list)):
            if tape:
                tape.append(node, frontier)
                for arg in node.args:
                    if not isinstance(arg, IOArgument): continue
                    # FIXME: use copy
                    frontier[arg.value.name] = copy(frontier[arg.value.name])
            try:
                r = node.invoke(frontier)
            except Exception as e:
                print("Failure in running `%s`" % node)
                raise
            for var in abandon:
                frontier.pop(var.name)
            logger.info("Removed from frontier %s, new size %d", abandon, len(frontier))
            frontier.update(r)

        r = [frontier[vn] for vn in vout]
        if squeeze:
            r = r[0]
        if return_tape:
            r = r, tape
        return r

    def gradient(self, tape):
        code = CodeSegment(self.engine)

        if hasattr(self.engine, "Add"):
            add = self.engine.Add
        else:
            @primitive(ain=['x1', 'x2'], aout=['y'])
            def add(engine, x1, x2, y):
                y[...] = x1 + x2

        ocd = {} # number of times seen
        for node, d in tape.records[::-1]:
            vjp = node.instr.vjp
            kwargs = {}
            partials = []
            for arg in node.args:
                if isinstance(arg, OArgument) \
                and '_' + arg.name in vjp.argnames:
                    kwargs['_' + arg.name] = '_' + arg.value.name
                if isinstance(arg, (IArgument, IOArgument)) \
                and arg.name in vjp.argnames:
                    value, version = d[arg.value.name]
                    kwargs[arg.name] = value

                if isinstance(arg, (IArgument, IOArgument)) \
                and '_' + arg.name in vjp.argnames:
                    occ = ocd.get(arg.value, 0)
                    ocd[arg.value] = occ + 1
                    if occ == 0:
                        # directly write to the gradient, it is used
                        kwargs['_' + arg.name] = '_' + arg.value.name
                    else:
                        newname = '_' + arg.value.name + '#partial'
                        kwargs['_' + arg.name] = newname
                        partials.append((newname, '_' + arg.value.name))
                if isinstance(arg, EXArgument):
                    kwargs[arg.name] = arg.value

            node = vjp.create_node(self.engine, kwargs)
            code.append(node)
            for p, r in partials:
                kwargs = {}
                kwargs['x1'] = p
                kwargs['x2'] = r
                kwargs['y'] = r
                node = add.create_node(self.engine, kwargs)
                code.append(node)
        return code

    def compute_with_gradient(self, vout, init, ginit, return_tape=False):
        if not isinstance(vout, (tuple, list, set)):
            vout = [vout]
            squeeze = True
        else:
            squeeze = False

        cnout = [vn for vn in vout if not vn.startswith('_')]
        # if gradient request are requested, they must be computed
        cnout_g = [ vn[1:] for vn in ginit]

        gnout = [vn for vn in vout if vn.startswith('_')]

        cout, tape = self.compute(cnout + cnout_g, init, return_tape=True)
        cout = cout[:len(cnout)]

        gradient = self.gradient(tape)

        _init = init.copy()
        _init.update(ginit)

        gout = gradient.compute(gnout, _init)
        d = {}
        d.update(zip(cnout, cout))
        d.update(zip(gnout, gout))

        out = [d[vn] for vn in vout]
        if squeeze:
            out = out[0]
        return out

    def __repr__(self):
        nodes = '\n'.join('%s' % node for node in self.nodes)
        refs = '%s' % self.refs
        return '\n'.join([nodes, refs])
from .zero import ZERO
