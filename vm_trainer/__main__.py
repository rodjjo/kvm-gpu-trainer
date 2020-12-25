import sys

import click

from .management import device_info, machines, network  # noqa
from .management.clickgroup import cli
from .exceptions import CommandError


def main():
    try:
        cli()
    except CommandError as e:
        click.echo(e.args[0])
        sys.exit(1)


main()
