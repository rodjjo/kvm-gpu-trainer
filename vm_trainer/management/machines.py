import os
from typing import Union

import click

from subprocess import check_call, CalledProcessError

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
@click.option("--tpm", required=False, default=True, type=bool, help="Use TPM or Not")
def machine_create(name: str, cpus: int, memory: int, existing_disk: Union[str, None], disk_size: Union[int, None], tpm: bool) -> None:
    DependencyManager.check_all()
    machine = Machine(name)
    if machine.exists():
        raise CommandError(f"The VM {name} already exists.")

    machine.set_cpus(cpus)
    machine.set_tpm(tpm)

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
def machine_set_cpus(name: str, cpus: int) -> None:
    machine = Machine(name)
    machine.must_exists()
    machine.set_cpus(cpus)
    machine.save()


@cli.command(help="Define the machine memory")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--memory", required=True, type=int, help="Amount of memory in MB")
def machine_set_memory(name: str, memory: int) -> None:
    machine = Machine(name)
    machine.must_exists()
    machine.set_memory(memory)
    machine.save()


@cli.command(help="Pass throug a USB device")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--address", required=True, type=str)
def machine_set_usb_device(name: str, address: str) -> None:
    machine = Machine(name)
    machine.must_exists()
    machine.set_usb_device(address)
    machine.save()


@cli.command(help="List existing machine names")
def machine_list() -> None:
    settings = Settings()
    for name in os.listdir(settings.machines_dir()):
        if not name.endswith('.yaml'):
            continue
        click.echo(name[0:-5])


@cli.command(help="Assign gpu's to an existing machine")
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_set_gpus(name: str) -> None:
    machine = Machine(name)
    machine.must_exists()
    machine.select_gpus()
    machine.save()


@cli.command(help="Select a mouse from evdev devices")
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_select_mouse(name: str) -> None:
    machine = Machine(name)
    machine.must_exists()
    machine.select_mouse()
    machine.save()


@cli.command(help="Select a keyboard from evdev devices")
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_select_keyboard(name: str) -> None:
    machine = Machine(name)
    machine.must_exists()
    machine.select_keyboard()
    machine.save()


@cli.command(help='Create the virtual machine disk (qcow)')
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_create_disk(name: str) -> None:
    machine = Machine(name)
    machine.must_exists()
    machine.create_disk()


@cli.command(help="Add a physical disk device to the machine")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--device", required=True, help="The disk device to map into the machine")
def machine_set_disk_device(name: str, device: str) -> None:
    machine = Machine(name)
    machine.must_exists()
    machine.set_raw_disk(device)
    machine.save()


@cli.command(help="Run the machine with an iso attached on it")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--iso", required=True, help="The path to the iso file to attach")
def machine_run_with_iso(name: str, iso: str) -> None:
    machine = Machine(name)
    machine.must_exists()
    machine.execute(iso)


@cli.command(help="Run the machine")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--shared-dir", required=False, help="The name of the virtual machine")
def machine_run(name: str, shared_dir: Union[str, None]) -> None:
    machine = Machine(name)
    machine.must_exists()
    machine.execute(None, shared_dir)


@cli.command(help="Kills the qemu process")
def machine_kill() -> None:
    try:
        check_call(["sudo", "pkill", "-f", "qemu-system-x86_64"])
    except CalledProcessError:
        raise CommandError("Failed to kill the qemu process")
