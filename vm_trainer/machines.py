import os
from pathlib import Path

import click
import yaml

from .clickgroup import cli
from .exceptions import CommandError
from .settings import VMS_DIR
from .utils import check_compatible_device
from .yamldoc import Dumper, Loader


def get_machine_settings_filepath(machine_name):
    if not os.path.exists(VMS_DIR):
        os.makedirs(VMS_DIR)
    filepath = Path(VMS_DIR).joinpath(f"{machine_name}.yaml")
    return filepath


def update_machine_setting(machine_name, setting_name, value):
    filepath = get_machine_settings_filepath(machine_name)
    if not os.path.exists(filepath):
        raise CommandError(f'File not found: {filepath}')

    with open(filepath) as fp:
        machine_settings = yaml.load(fp, Loader=Loader)
        machine_settings["machine"][setting_name] = value

    with open(filepath, "w") as fp:
        yaml.dump(machine_settings, fp, Dumper=Dumper)


def check_device():
    error = check_compatible_device()
    if error:
        raise CommandError(error)


@cli.command(help="Create new machine settings")
@click.option("--name", required=True, help="Name to the virtual machine")
@click.option("--cpus", default="-1", type=int, help="Number of cpu cores (default = -1 all cores)")
@click.option("--disk-size", required=True, type=int, help="Disk space in MB")
@click.option("--memory", required=True, type=int, help="Amount of memory in MB")
def machine_create(name: str, cpus: int, memory: int, disk_size: int):
    check_device()
    filepath = get_machine_settings_filepath(name)
    if os.path.exists(filepath):
        raise CommandError(f"The VM {name} already exists. File: {filepath}")
    machine = {
        "machine": {
            "name": name,
            "cpus": cpus,
            "memory": memory,
            "disk-size": disk_size
        }
    }
    with open(filepath, "w") as fp:
        yaml.dump(machine, fp, Dumper=Dumper)


@cli.command(help="Change the number of cpu cores used by an existing machine")
@click.option("--name", required=True, help="Name to the virtual machine")
@click.option("--cpus", default="-1", type=int, help="Number of cpu cores (default = -1 all cores)")
def machine_set_cpus(name, cpus):
    check_device()
    update_machine_setting(name, "cpus", cpus)


@cli.command(help="Change the amount of memory RAM of an existing machine")
@click.option("--name", required=True, help="Name to the virtual machine")
@click.option("--memory", required=True, type=int, help="Amount of memory in MB")
def machine_set_memory(name, memory):
    check_device()
    update_machine_setting(name, "memory", memory)


@cli.command(help="List existing machine names")
def machine_list():
    for name in os.listdir(VMS_DIR):
        if not name.endswith('.yaml'):
            continue
        click.echo(name[0:-5])
