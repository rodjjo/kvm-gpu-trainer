

try:
    from yaml import CDumper as Dumper  # noqa
    from yaml import CLoader as Loader  # noqa
except ImportError:
    from yaml import Dumper, Loader  # noqa
