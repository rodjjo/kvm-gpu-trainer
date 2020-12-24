import click
from .clickgroup import cli
from .utils import get_IOMMU_information, get_iommu_devices, gpus_from_iommu_devices


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
        click.echo(f"Addresses, video: [{gpu.video_address[0]}:{gpu.video_address[1]}] audio: [{gpu.audio_address[0]}:{gpu.audio_address[1]}]")
