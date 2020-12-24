import os
from pathlib import Path

import click
import yaml

from .clickgroup import cli
from .exceptions import CommandError
from .settings import VMS_DIR
from .utils import check_compatible_device, gpus_from_iommu_devices, create_qcow_disk
from .yamldoc import Dumper, Loader


def get_machine_settings_filepath(machine_name):
    if not os.path.exists(VMS_DIR):
        os.makedirs(VMS_DIR)
    filepath = Path(VMS_DIR).joinpath(f"{machine_name}.yaml")
    return filepath


def load_machine_settings(machine_name):
    filepath = get_machine_settings_filepath(machine_name)
    if not os.path.exists(filepath):
        raise CommandError(f'File not found: {filepath}')

    with open(filepath) as fp:
        return yaml.load(fp, Loader=Loader)


def get_machine_disk_filepath(machine_name):
    disk_dir = VMS_DIR.joinpath(f"{machine_name}-disks")
    if not os.path.exists(disk_dir):
        os.makedirs(disk_dir)
    return disk_dir.joinpath(f"{machine_name}.qcow")


def create_disk(machine_name):
    settings = load_machine_settings(machine_name)
    disk_filepath = get_machine_disk_filepath(machine_name)
    if os.path.exists(disk_filepath):
        raise CommandError(f'The machine disk already exists at {disk_filepath}')
    disk_size = settings["machine"]["disk-size"]
    if disk_size < 5000:
        raise CommandError('The machine configuration has a very small disk. Operation Aborted')

    for line in create_qcow_disk(disk_filepath, disk_size):
        click.echo(line)


def update_machine_setting(machine_name, setting_name, value):
    machine_settings = load_machine_settings(machine_name)
    machine_settings["machine"][setting_name] = value

    filepath = get_machine_settings_filepath(machine_name)
    with open(filepath, "w") as fp:
        yaml.dump(machine_settings, fp, Dumper=Dumper)


def check_device():
    error = check_compatible_device()
    if error:
        raise CommandError(error)


@cli.command(help="Create new machine settings")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--cpus", default="-1", type=int, help="Number of cpu cores (default = -1 all cores)")
@click.option("--disk-size", required=True, type=int, help="Disk space in MB")
@click.option("--memory", required=True, type=int, help="Amount of memory in MB")
def machine_create(name: str, cpus: int, memory: int, disk_size: int):
    check_device()
    filepath = get_machine_settings_filepath(name)
    if os.path.exists(filepath):
        raise CommandError(f"The VM {name} already exists. File: {filepath}")

    if cpus < -1:
        raise CommandError("Invalid cpu count")

    if disk_size < 5000:
        raise CommandError("Disk size too small. Expected 5000 or more")

    if memory < 256:
        raise CommandError("Memory too small. Expected 256 or more")

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

    create_disk(name)


@cli.command(help="Change the number of cpu cores used by an existing machine")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--cpus", default="-1", type=int, help="Number of cpu cores (default = -1 all cores)")
def machine_set_cpus(name, cpus):
    check_device()
    update_machine_setting(name, "cpus", cpus)


@cli.command(help="Change the amount of memory RAM of an existing machine")
@click.option("--name", required=True, help="The name of the virtual machine")
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


@cli.command(help="Assign gpu's to an existing machine")
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_set_gpus(name):
    gpus = sorted(gpus_from_iommu_devices(), key=lambda gpu: gpu.video_vendor)
    if not gpus:
        raise CommandError("There is no GPU avaliable on this device")

    click.echo('Choose one or more gpu type the numbers separated by an comma:')

    for index, gpu in enumerate(gpus):
        click.echo(f"{index} - {gpu.video_vendor} video-address: [{gpu.video_address[0]}:{gpu.video_address[1]}]")

    user_input = input('Type the gpu numbers to use (comma separated):')

    if not user_input.strip():
        raise CommandError('No options were selected')

    selected_gpus = []
    indexes = set()
    for option in user_input.split(','):
        index = int(option)
        if index < 0 or index >= len(gpus):
            raise CommandError(f'{index} is not a valid option')
        if index in indexes:
            raise CommandError(f'The gpu number {index} is duplicated in your selection')
        indexes.add(index)
        selected_gpus.append(gpus[index])

    data = []
    for gpu in selected_gpus:
        item = {
            "video": {
                "address": gpu.video_address[0],
                "offset": gpu.video_address[1],
            }
        }
        if len(gpu.audio_address):
            item["audio"] = {
                "address": gpu.audio_address[0],
                "offset": gpu.audio_address[1],
            }
        data.append(item)
    update_machine_setting(name, "gpus", data)


@cli.command(help='Create the virtual machine disk (qcow)')
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_create_disk(name):
    create_disk(name)
