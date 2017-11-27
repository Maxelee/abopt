class ModelError(Exception): pass

class UnpackError(ModelError): pass
class DuplicatedOutput(ModelError): pass
class MissingArgument(ModelError): pass
class OverwritePrecaution(ModelError): pass
class UnexpectedOutput(ModelError): pass
class ResolveError(ModelError): pass
class InferError(ModelError): pass
