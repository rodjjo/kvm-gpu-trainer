import os
import subprocess
import re

from vm_trainer.utils import run_read_output
from vm_trainer.exceptions import CommandError


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
    def is_physical_interface(filepath):
        try:
            target_path = os.readlink(filepath)
        except OSError:
            target_path = ""
        if TapNetwork.PHYSICAL_INTERFACE_RE.search(target_path):
            return True
        return False

    @staticmethod
    def get_logical_interfaces():
        for name in os.listdir("/sys/class/net/"):
            if name not in ("..", ".") and not TapNetwork.is_physical_interface(os.path.join("/sys/class/net/", name)):
                yield name

    @staticmethod
    def get_mac(name):
        with open(f"/sys/class/net/{name}/address", "r") as fp:
            return fp.read().strip()

    @staticmethod
    def tap_interface_exists():
        logical_ifs = TapNetwork.get_logical_interfaces()
        if TapNetwork.TAP_INTERFACE_NAME in logical_ifs:
            return True
        if TapNetwork.BRIDGE_INTERFACE_NAME in logical_ifs:
            return True
        return False

    @staticmethod
    def add_tap_network(target_interface, ip_address):
        if TapNetwork.tap_interface_exists():
            raise CommandError(f"The tap network interface {TapNetwork.TAP_INTERFACE_NAME} is already configured.")

        target_mac = TapNetwork.get_mac(target_interface)
        if not target_mac:
            raise CommandError(f"Unable to get the mac address of {target_interface} interface")

        try:
            subprocess.check_call(["sudo", "ip", "link", "add", "name", TapNetwork.BRIDGE_INTERFACE_NAME, "type", "bridge"])
            subprocess.check_call(["sudo", "ip", "addr", "add", "dev", TapNetwork.BRIDGE_INTERFACE_NAME, ip_address])
            subprocess.check_call(["sudo", "ip", "link", "set", "dev", TapNetwork.BRIDGE_INTERFACE_NAME, "address", target_mac])
            subprocess.check_call(["sudo", "ip", "link", "set", TapNetwork.BRIDGE_INTERFACE_NAME, "up"])
            subprocess.check_call(["sudo", "ip", "tuntap", "add", "dev", TapNetwork.TAP_INTERFACE_NAME, "mode", "tap"])
            subprocess.check_call(["sudo", "ip", "link", "set", TapNetwork.TAP_INTERFACE_NAME, "master", TapNetwork.BRIDGE_INTERFACE_NAME])
            subprocess.check_call(["sudo", "ip", "link", "set", target_interface, "up"])
            subprocess.check_call(["sudo", "ip", "link", "set", TapNetwork.TAP_INTERFACE_NAME, "up"])
            subprocess.check_call(["sudo", "iptables", "-t", "nat", "-A", "POSTROUTING", "-o", target_interface, "-j", "MASQUERADE"])
            subprocess.check_call(["sudo", "iptables", "-A", "FORWARD", "-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED", "-j", "ACCEPT"])
            subprocess.check_call(["sudo", "iptables", "-A", "FORWARD", "-i", TapNetwork.BRIDGE_INTERFACE_NAME, "-o", target_interface, "-j", "ACCEPT"])
        except subprocess.CalledProcessError as e:
            raise CommandError(e.args[0])

    @staticmethod
    def remove_tap_network(target_interface):
        try:
            subprocess.check_call(["sudo", "ip", "tuntap", "del", "dev", TapNetwork.TAP_INTERFACE_NAME, "mode", "tap"])
        except subprocess.CalledProcessError:
            pass
        try:
            subprocess.check_call(["sudo", "ip", "link", "set", TapNetwork.BRIDGE_INTERFACE_NAME, "down"])
        except subprocess.CalledProcessError:
            pass
        try:
            subprocess.check_call(["sudo", "ip", "link", "delete", TapNetwork.BRIDGE_INTERFACE_NAME, "type", "bridge"])
        except subprocess.CalledProcessError:
            pass
        try:
            subprocess.check_call(["sudo", "ip", "link", "set", "up", "dev", target_interface])
        except subprocess.CalledProcessError:
            pass
