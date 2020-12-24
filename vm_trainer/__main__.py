import sys

import click

from . import device_info  # noqa
from . import machines  # noqa
from .clickgroup import cli
from .exceptions import CommandError


def main():
    try:
        cli()
    except CommandError as e:
        click.echo(e.args[0])
        sys.exit(1)


main()
