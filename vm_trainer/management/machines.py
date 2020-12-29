import os
from typing import Union

import click

from vm_trainer.components.dependencies import DependencyManager
from vm_trainer.components.machine import Machine
from vm_trainer.exceptions import CommandError
from vm_trainer.management.clickgroup import cli
from vm_trainer.settings import Settings


@cli.command(help="Create new machine settings")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--cpus", default="-1", type=int, help="Number of cpu cores (default = -1 all cores)")
@click.option("--disk-size", required=False, type=int, help="Disk space in MB")
@click.option("--existing-disk", required=False, type=str, help="Use an existing disk")
@click.option("--memory", required=True, type=int, help="Amount of memory in MB")
def machine_create(name: str, cpus: int, memory: int, existing_disk: Union[str, None], disk_size: Union[int, None]):
    DependencyManager.check_all()
    machine = Machine(name)
    if machine.exists():
        raise CommandError(f"The VM {name} already exists.")

    machine.set_cpus(cpus)

    if cpus < -1:
        raise CommandError("Invalid cpu count")

    if existing_disk:
        machine.set_disk_path(existing_disk)
    elif disk_size is not None:
        machine.set_disk_size(disk_size)
    else:
        raise CommandError("No disk settings were specified")

    machine.set_memory(memory)
    machine.save()

    try:
        machine.create_disk()
    except CommandError:
        pass


@cli.command(help="Define the number of cpu cores to use")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--cpus", default="-1", type=int, help="Number of cpu cores (default = -1 all cores)")
def machine_set_cpus(name, cpus):
    machine = Machine(name)
    machine.must_exists()
    machine.set_cpus(cpus)
    machine.save()


@cli.command(help="Define the machine memory")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--memory", required=True, type=int, help="Amount of memory in MB")
def machine_set_memory(name, memory):
    machine = Machine(name)
    machine.must_exists()
    machine.set_memory(memory)
    machine.save()


@cli.command(help="List existing machine names")
def machine_list():
    settings = Settings()
    for name in os.listdir(settings.machines_dir()):
        if not name.endswith('.yaml'):
            continue
        click.echo(name[0:-5])


@cli.command(help="Assign gpu's to an existing machine")
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_set_gpus(name):
    machine = Machine(name)
    machine.must_exists()
    machine.select_gpus()
    machine.save()


@cli.command(help="Select a mouse from evdev devices")
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_select_mouse(name):
    machine = Machine(name)
    machine.must_exists()
    machine.select_mouse()
    machine.save()


@cli.command(help="Select a keyboard from evdev devices")
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_select_keyboard(name):
    machine = Machine(name)
    machine.must_exists()
    machine.select_keyboard()
    machine.save()


@cli.command(help='Create the virtual machine disk (qcow)')
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_create_disk(name):
    machine = Machine(name)
    machine.must_exists()
    machine.create_disk()


@cli.command(help="Add a physical disk device to the machine")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--device", required=True, help="The disk device to map into the machine")
def machine_set_disk_device(name, device):
    machine = Machine(name)
    machine.must_exists()
    machine.set_raw_disk(device)
    machine.save()


@cli.command(help="Run the machine with an iso attached on it")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--iso", required=True, help="The path to the iso file to attach")
def machine_run_with_iso(name, iso):
    machine = Machine(name)
    machine.must_exists()
    machine.execute(iso)


@cli.command(help="Run the machine")
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_run(name):
    machine = Machine(name)
    machine.must_exists()
    machine.execute()
