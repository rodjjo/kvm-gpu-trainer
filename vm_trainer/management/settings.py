import click

from vm_trainer.management.clickgroup import cli
from vm_trainer.settings import Settings


@cli.command(help="Set the default disk directory for the machines")
@click.option("--path", required=True, type=str, help="The path to the directory")
def settings_set_disk_dir(path: str) -> None:
    settings = Settings()
    settings.set_disk_directory(path)
    settings.save()


@cli.command(help="Set the main network interface to connect the bridge with")
@click.option("--name", required=True, type=str, help="The interface name")
def settings_set_network_interface(name: str) -> None:
    settings = Settings()
    settings.set_network_interface(name)
    settings.save()


@cli.command(help="Set the main network interface to connect the bridge with")
def settings_show_network_interface() -> None:
    settings = Settings()
    click.echo(settings.network_interface())


@cli.command(help="Show the default disk directory for the machines")
def settings_show_disk_dir() -> None:
    settings = Settings()
    click.echo(settings.disk_directory())


@cli.command(help="Set the bridge network interface's IP address")
@click.option("--ip", required=True, type=str, help="The path to the directory")
def settings_set_ip_address(ip: str) -> None:
    settings = Settings()
    if not ip.endswith("/24"):
        ip += "/24"
    settings.set_network_ip(ip)
    settings.save()


@cli.command(help="Show the bridge network interface's IP address")
def settings_show_ip_address() -> None:
    settings = Settings()
    click.echo(settings.network_ip())
