import os
import sys

import click

import vm_trainer.management  # noqa
from vm_trainer.exceptions import CommandError
from vm_trainer.management.clickgroup import cli


def main():
    try:
        if os.geteuid() == 0:
            raise CommandError("vm_trainer can't be executed by the root user. Please do not use sudo.")
        cli()
    except CommandError as e:
        click.echo(e.args[0])
        sys.exit(1)


main()
