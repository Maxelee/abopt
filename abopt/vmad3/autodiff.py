from .symbol import ZeroLiteral, Literal, Symbol
from .model import Model
from .operator import terminal, add

def find_primitive_type(p, func):
    # we will only do this on the opr primitives
    # because otherwise this is undefined
    # the algebra of autodiff in vmad3 is explicitly not closed!
    assert isinstance(p, type(p).operator.opr)

    assert func in ['vjp', 'jvp', 'opr']

    if func == 'jvp': return p.operator.jvp
    if func == 'vjp': return p.operator.vjp
    if func == 'opr': return p.operator.opr

def prepare_opr_kwargs(record, model):
    p = record.node
    impl_kwargs = record.impl_kwargs

    kwargs = {}
    kwargs.update(p.kwargs)

    # convert original arguments to literals
    for k, v in impl_kwargs.items():
        if k in p.varin:
            kwargs[k] = Literal(model, v)
        else:
            kwargs[k] = v

    return kwargs

def vjp(tape):
    model = Model()
    for var in tape.model._vout:
        model.input(var.vjp_name)

    for i, record in enumerate(tape[::-1]):
        p = record.node
        impl_kwargs = record.impl_kwargs

        vjp_of_p = find_primitive_type(p, func='vjp')

        kwargs = prepare_opr_kwargs(record, model)

        # initialize 'v'
        for argname, var in p.varout.items():
            kwargs['_' + argname] = model.get(var.vjp_name)

        # create output vjps
        for argname, var in p.varin.items():
            # bypass literal arguments
            if isinstance(var, Literal): continue

            reference_id = p.varin_info[argname]
            if reference_id == len(var.references):
                # largest reference_id, must be the
                # first time seeing the partial derivative
                # define the symbol for the full derivative
                var_p = model.define(var.vjp_name)
            else:
                var_p = model.define(var.vjp_name + '#%d' % reference_id)

            kwargs['_' + argname] = var_p

        node = vjp_of_p(**kwargs)

        # combine partial derivatives.
        for argname, var in p.varin.items():
            # bypass literal arguments
            if isinstance(var, Literal): continue
            reference_id = p.varin_info[argname]
            # accummulate the partials
            if reference_id != len(var.references):
                var_f = model.get(var.vjp_name)
                var_p = model.get(var.vjp_name + '#%d' % reference_id)
                # create a new symbol for the result, with the same name
                # because we intent to overwrite it.
                var_f2 = model.define(var.vjp_name)

                add(x1=var_f, x2=var_p, y=var_f2)

    # mark outputs
    for var in tape.model._vin:
        if not model.has(var.vjp_name):
            varout = ZeroLiteral(model)
        else:
            varout = model.get(var.vjp_name)
        model.output(**{var.vjp_name : varout})

    return model

def jvp(tape):
    model = Model()
    for var in tape.model._vin:
        model.input(var.jvp_name)

    for i, record in enumerate(tape):
        p = record.node
        impl_kwargs = record.impl_kwargs

        jvp_of_p = find_primitive_type(p, func='jvp')

        kwargs = prepare_opr_kwargs(record, model)

        # initialize 'v'
        for argname, var in p.varin.items():
            if isinstance(var, Literal):
                jvp_var = ZeroLiteral(model)
            else:
                jvp_var = model.get(var.jvp_name)
            kwargs[argname + '_'] = jvp_var

        # create output symbols
        for argname, var in p.varout.items():
            jvp_var = model.define(var.jvp_name)
            kwargs[argname + '_'] = jvp_var

        jvp_of_p(**kwargs)

    # mark outputs
    for var in tape.model._vout:
        if not model.has(var.jvp_name):
            varout = ZeroLiteral(model)
        else:
            varout = model.get(var.jvp_name)
        model.output(**{var.jvp_name : varout})

    return model
