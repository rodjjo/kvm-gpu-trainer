import click

from vm_trainer.components.network import TapNetwork
from vm_trainer.management.clickgroup import cli
from vm_trainer.settings import Settings


@cli.command(help="Show logical network interfaces")
def network_show_logical() -> None:
    for interface in TapNetwork.get_logical_interfaces():
        click.echo(interface)


@cli.command(help="Show pyisical network interfaces")
def network_show_physical() -> None:
    for interface in TapNetwork.get_physical_interfaces():
        click.echo(interface)


@cli.command(help="Show the interface MAC address")
@click.option("--name", required=True, help="The network interface's name")
def network_show_mac(name: str) -> None:
    click.echo(TapNetwork.get_mac(name))


@cli.command(help="Add vmtrainer network interfaces")
@click.option("--target", required=True, help="The network interface's name with internet access (physical interface)")
def network_add_tap(target: str) -> None:
    settings = Settings()
    TapNetwork.add_tap_network(target, settings.network_ip())


@cli.command(help="Remove vmtrainer network interfaces")
def network_del_tap() -> None:
    TapNetwork.remove_tap_network()
