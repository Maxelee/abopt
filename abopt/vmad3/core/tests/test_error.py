from abopt.vmad3.core.model import Builder
from abopt.vmad3.core.operator import add
import pytest

def test_error_infer():
    from abopt.vmad3.core.error import InferError
    with Builder() as m:
        a = m.input('a')
        with pytest.raises(InferError):
            add(x1=1, x2=1)

def test_error_bad_arg1():
    from abopt.vmad3.core.error import BadArgument
    with Builder() as m:
        a = m.input('a')
        with pytest.raises(BadArgument):
            add(1, 1, 1)

def test_error_bad_arg2():
    from abopt.vmad3.core.error import BadArgument
    with Builder() as m:
        a = m.input('a')
        with pytest.raises(BadArgument):
            add(1, x1=1, x2=2)

def test_error_missing():
    from abopt.vmad3.core.error import MissingArgument
    with Builder() as m:
        a = m.input('a')
        with pytest.raises(MissingArgument):
            add(x2=1)

def test_error_overwrite():
    from abopt.vmad3.core.error import OverwritePrecaution
    with Builder() as m:
        a = m.input('a')
        with pytest.raises(OverwritePrecaution):
            add(x1=a, x2=a, y=a)

def test_error_many_output():
    from abopt.vmad3.core.error import DuplicatedOutput
    with Builder() as m:
        a = m.input('a')
        with pytest.raises(DuplicatedOutput):
            m.output(a=a)
            m.output(a=a)


def test_error_unexpected_output():
    from abopt.vmad3.core.error import UnexpectedOutput
    with Builder() as m:
        a = m.input('a')
        m.output(a=a)

    with pytest.raises(UnexpectredOutput):
        m.compute(vout='b', init=dict(a=1.0))

def test_error_unexpected_output():
    from abopt.vmad3.core.error import ResolveError
    with Builder() as m:
        a = m.input('a')
        m.output(a=a)

    with pytest.raises(ResolveError):
        m.compute(vout='a', init={})
