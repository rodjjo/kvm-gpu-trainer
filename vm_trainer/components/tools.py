import os
import subprocess
from getpass import getuser
from pathlib import Path
from typing import List, Union

import click

from vm_trainer.exceptions import CommandError
from vm_trainer.settings import Settings
from vm_trainer.utils import run_read_output

CommandArgs = List[str]

SCREAM_SERVICE_CONFIG = [
    "[Unit]",
    "Description=Scream IVSHMEM pulse reciever",
    "After=pulseaudio.service",
    "Wants=pulseaudio.service",
    "",
    "[Service]",
    "Type=simple",
    "ExecStartPre=/usr/bin/truncate -s 0 /dev/shm/scream-ivshmem",
    "ExecStartPre=/usr/bin/dd if=/dev/zero of=/dev/shm/scream-ivshmem bs=1M count=2",
    "ExecStart=/usr/bin/scream -m /dev/shm/scream-ivshmem -o pulse",
    "",
    "[Install]",
    "WantedBy=default.target",
]


class ToolBase(object):
    TOOL_NAME = "replace-me"
    DO_NOTHING_PARAMETER = "--version"

    @staticmethod
    def execute_application(parameters: CommandArgs, cwd: Union[str, None] = None) -> None:
        try:
            kwargs = {}
            if cwd:
                kwargs["cwd"] = cwd
            subprocess.check_call(parameters, **kwargs)  # type: ignore
        except subprocess.CalledProcessError as e:
            raise CommandError(e.args[0])

    def execute(self, parameters: CommandArgs) -> None:
        self.execute_application([self.TOOL_NAME] + parameters)

    def execute_as_super(self, parameters: CommandArgs) -> None:
        self.execute_application(["sudo", self.TOOL_NAME] + parameters)

    def install(self, show_message: bool = False) -> None:
        raise NotImplementedError()

    def exists(self, show_message: bool = False) -> bool:
        with open(os.devnull, "w") as nullfp:
            try:
                subprocess.check_call([self.TOOL_NAME, self.DO_NOTHING_PARAMETER], stdout=nullfp)
                if show_message:
                    click.echo(self.alread_installed_message())
                return True
            except FileNotFoundError:
                pass
            return False

    def must_exists(self) -> None:
        if not self.exists():
            raise CommandError(f"The tool {self.TOOL_NAME} is not present in your system")

    def alread_installed_message(self) -> str:
        return f"The tool {self.TOOL_NAME} is already installed"


class PackageManagementTool(ToolBase):
    def update(self) -> None:
        raise NotImplementedError()

    def install_qemu_kvm(self) -> None:
        raise NotImplementedError()

    def install_scream(self) -> None:
        raise NotImplementedError()

    def install_git(self) -> None:
        raise NotImplementedError()

    def install_build_essential(self) -> None:
        raise NotImplementedError()

    def configure_user_access(self) -> None:
        self.execute_as_super(["sudo", "usermod", "-aG", "libvirt,libvirtd,kvm", getuser()])

    def enable_virtd(self) -> None:
        self.execute_application(["sudo", "systemctl", "enable", "libvirtd.service"])
        self.execute_application(["sudo", "systemctl", "start", "libvirtd.service"])

    def virtd_check_status(self) -> None:
        self.execute_application(["sudo", "systemctl", "--no-pager", "status", "libvirtd.service"])


class PacmanTool(PackageManagementTool):
    TOOL_NAME = "pacman"

    def update(self) -> None:
        self.execute_as_super(["-Syy"])

    def install_qemu_kvm(self) -> None:
        self.update()
        self.execute_as_super(["-S", "qemu", "virt-manager", "virt-viewer", "dnsmasq", "vde2", "bridge-utils", "openbsd-netcat"])
        self.execute_as_super(["-S", "ebtables", "iptables"])
        self.enable_virtd()
        self.configure_user_access()
        self.virtd_check_status()

    def install_scream(self) -> None:
        clone_dirpath = GitTool().clone('https://aur.archlinux.org/scream.git', 'scream')
        self.execute_application(['makepkg'], cwd=clone_dirpath)

        binary_path = os.path.join(clone_dirpath, "pkg/scream/usr/bin/scream")
        self.execute_application(['sudo', 'cp', binary_path, "/usr/bin/scream"])

        scream_service_path = Path.expanduser(Path("~/.config/systemd/user/scream-ivshmem-pulse.service"))
        with open(scream_service_path, "w") as fp:
            fp.writelines(SCREAM_SERVICE_CONFIG)
        self.execute_application(["systemctl", "enable", "--user", "scream-ivshmem-pulse"])
        self.execute_application(["systemctl", "start", "--user", "scream-ivshmem-pulse"])

    def install_build_essential(self) -> None:
        self.update()
        self.execute_as_super(["-S", "base-devel"])

    def install_git(self) -> None:
        self.update()
        self.execute_as_super(["-S", "git"])


class AptGetTool(PackageManagementTool):
    TOOL_NAME = "apt-get"

    def update(self) -> None:
        self.execute_as_super(["update"])

    def install_qemu_kvm(self) -> None:
        self.update()
        self.execute_as_super(["install", "qemu-kvm", "libvirt-daemon-system", "libvirt-clients", "bridge-utils"])
        self.enable_virtd()
        self.configure_user_access()
        self.virtd_check_status()


class IpTool(ToolBase):
    TOOL_NAME = "ip"
    DO_NOTHING_PARAMETER = "-V"

    def get_mac_address(self, name: str) -> str:
        with open(f"/sys/class/net/{name}/address", "r") as fp:
            return fp.read().strip()

    def interface_exists(self, name: str) -> bool:
        try:
            data = "".join(run_read_output(["ip", "-o", "link", "show", name])).strip()
        except subprocess.CalledProcessError:
            data = ""
        return name in data

    def create_bridge_interface(self, name: str, ip_address: str) -> None:
        if self.interface_exists(name):
            return
        self.execute_as_super(["link", "add", "name", name, "type", "bridge"])
        self.execute_as_super(["addr", "add", "dev", name, ip_address])
        self.execute_as_super(["link", "set", name, "up"])

    def create_tap_interface(self, name: str, bridge_name: str) -> None:
        if self.interface_exists(name):
            return
        self.execute_as_super(["tuntap", "add", "dev", name, "mode", "tap"])
        self.execute_as_super(["link", "set", name, "master", bridge_name])
        self.execute_as_super(["link", "set", name, "up"])

    def remove_tap_interface(self, name: str) -> None:
        if not self.interface_exists(name):
            return
        try:
            self.execute_as_super(["tuntap", "del", "dev", name, "mode", "tap"])
        except CommandError:
            pass

    def remove_bridge_interface(self, name: str) -> None:
        if not self.interface_exists(name):
            return
        try:
            self.execute_as_super(["link", "set", name, "down"])
        except CommandError:
            pass
        try:
            self.execute_as_super(["link", "delete", name, "type", "bridge"])
        except CommandError:
            pass


class EmulatorTool(ToolBase):
    TOOL_NAME = "qemu-system-x86_64"
    DO_NOTHING_PARAMETER = "-version"

    def install(self, show_message: bool = True) -> None:
        if self.exists(show_message):
            return
        PackageTool().install_qemu_kvm()


class IpTablesTool(ToolBase):
    TOOL_NAME = "iptables"

    def create_nat_routing(self, bridge_interface: str, target_interface: str) -> None:
        self.execute_as_super(["-t", "nat", "-A", "POSTROUTING", "-o", target_interface, "-j", "MASQUERADE"])
        self.execute_as_super(["-A", "FORWARD", "-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED", "-j", "ACCEPT"])
        self.execute_as_super(["-A", "FORWARD", "-i", bridge_interface, "-o", target_interface, "-j", "ACCEPT"])


class GitTool(ToolBase):
    TOOL_NAME = "git"

    def install(self, show_message: bool = True) -> None:
        if self.exists(False):
            return
        PackageTool().install_git()
        if not self.exists(False):
            raise CommandError("Could not install git tool")

    def clone(self, url: str, dir_name: str) -> str:
        if not self.exists(False):
            PackageTool().install_git()
        if not self.exists(False):
            raise CommandError("The git tool is required to install scream.")
        settings = Settings()
        clone_path = os.path.join(settings.temp_dir(), dir_name)
        self.execute(['clone', url, clone_path])
        return clone_path


PackageTool = PacmanTool if PacmanTool().exists() else AptGetTool
