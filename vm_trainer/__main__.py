import sys

import click

import vm_trainer.management  # noqa
from .management.clickgroup import cli
from .exceptions import CommandError


def main():
    try:
        cli()
    except CommandError as e:
        click.echo(e.args[0])
        sys.exit(1)


main()
