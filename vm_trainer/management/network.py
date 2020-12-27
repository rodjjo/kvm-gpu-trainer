import click
from .clickgroup import cli
from vm_trainer.components.network import TapNetwork


@cli.command(help="Show logical network interfaces")
def network_show_logical():
    for interface in TapNetwork.get_logical_interfaces():
        click.echo(interface)


@cli.command(help="Show pyisical network interfaces")
def network_show_physical():
    for interface in TapNetwork.get_physical_interfaces():
        click.echo(interface)


@cli.command(help="Show the interface MAC address")
@click.option("--name", required=True, help="The network interface's name")
def network_show_mac(name):
    click.echo(TapNetwork.get_mac(name))


@cli.command(help="Add vmtrainer network interfaces")
@click.option("--target", required=True, help="The network interface's name with internet access (physical interface)")
def network_add_tap(target):
    TapNetwork.add_tap_network(target, "192.168.66.1/24")


@cli.command(help="Remove vmtrainer network interfaces")
def network_del_tap():
    TapNetwork.remove_tap_network()
