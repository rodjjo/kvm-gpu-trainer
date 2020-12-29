import click

from vm_trainer.components.user_input import UserInput
from vm_trainer.management.clickgroup import cli
from vm_trainer.utils import (get_iommu_devices, get_IOMMU_information,
                              gpus_from_iommu_devices)


@cli.command(help="Show IOMMU information")
def show_iommu():
    for line in get_IOMMU_information():
        click.echo(line)


@cli.command(help="List devices in IOMMU groups")
def show_iommu_devices():
    for line in get_iommu_devices():
        click.echo(line)


@cli.command(help="List GPUs in IOMMU groups")
def show_gpus():
    for gpu in gpus_from_iommu_devices():
        click.echo(f"GPU: {gpu.video_vendor}")
        click.echo(f"Addresses, video: [0000:{gpu.video_address}] audio: [0000:{gpu.audio_address}]")


@cli.command(help="List avaliable evdev user inputs")
def user_input_list():
    for device in UserInput.list_devices():
        click.echo(device)


@cli.command(help="List avaliable evdev mouses")
def user_input_mouses():
    for device in UserInput.list_mouses():
        click.echo(device)


@cli.command(help="List avaliable evdev keyboards")
def user_input_keyboards():
    for device in UserInput.list_keyboards():
        click.echo(device)
