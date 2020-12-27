import os
import re
from typing import Iterator

from vm_trainer.components.tools import IpTablesTool, IpTool
from vm_trainer.utils import run_read_output


class TapNetwork(object):
    TAP_INTERFACE_NAME = "vmtrainertap0"
    BRIDGE_INTERFACE_NAME = "vmtrainerbr0"

    IP_LINK_NAME_RE = re.compile(r"[^:]+:[ ]+([^:]+):.*")
    PHYSICAL_INTERFACE_RE = re.compile(r"devices\/pci[0-9a-f]{4}:")

    @staticmethod
    def get_physical_interfaces():
        logical_ones = list(TapNetwork.get_logical_interfaces())
        for interface in run_read_output(["ip", "-o", "link", "show"]):
            match = TapNetwork.IP_LINK_NAME_RE.match(interface)
            if not match:
                continue
            if match.group(1) not in logical_ones:
                yield match.group(1)

    @staticmethod
    def is_physical_interface(filepath: str) -> bool:
        try:
            target_path = os.readlink(filepath)
        except OSError:
            target_path = ""
        if TapNetwork.PHYSICAL_INTERFACE_RE.search(target_path):
            return True
        return False

    @staticmethod
    def get_logical_interfaces() -> Iterator[str]:
        for name in os.listdir("/sys/class/net/"):
            if name not in ("..", ".") and not TapNetwork.is_physical_interface(os.path.join("/sys/class/net/", name)):
                yield name

    @staticmethod
    def get_mac(name: str) -> str:
        return IpTool().get_mac_address(name)

    @staticmethod
    def add_tap_network(target_interface: str, ip_address: str) -> None:
        ip_tool = IpTool()
        ip_tool.create_bridge_interface(TapNetwork.BRIDGE_INTERFACE_NAME, ip_address)
        ip_tool.create_tap_interface(TapNetwork.TAP_INTERFACE_NAME, TapNetwork.BRIDGE_INTERFACE_NAME)
        ip_tables = IpTablesTool()
        ip_tables.create_nat_routing(TapNetwork.BRIDGE_INTERFACE_NAME, target_interface)

    @staticmethod
    def remove_tap_network() -> None:
        ip_tool = IpTool()
        ip_tool.remove_tap_interface(TapNetwork.TAP_INTERFACE_NAME)
        ip_tool.remove_bridge_interface(TapNetwork.BRIDGE_INTERFACE_NAME)
