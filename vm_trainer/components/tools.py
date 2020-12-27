from getpass import getuser
import os
from pathlib import Path
import subprocess
from typing import List, NoReturn, Union

import click

from vm_trainer.exceptions import CommandError
from vm_trainer.settings import TEMP_DIR

CommandArgs = List[str]


class ToolBase(object):
    TOOL_NAME = "replace-me"
    DO_NOTHING_PARAMETER = "--version"

    @staticmethod
    def execute_application(parameters: CommandArgs, cwd: Union[str, None] = None) -> NoReturn:
        try:
            kwargs = {}
            if cwd:
                kwargs["cwd"] = cwd
            subprocess.check_call(parameters, **kwargs)
        except subprocess.CalledProcessError as e:
            raise CommandError(e.args[0])

    def execute(self, parameters: CommandArgs) -> NoReturn:
        self.execute_application([self.TOOL_NAME] + parameters)

    def execute_as_super(self, parameters: CommandArgs) -> NoReturn:
        self.execute_application(["sudo", self.TOOL_NAME] + parameters)

    def install(self, show_message: bool = False) -> NoReturn:
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

    def check_exists(self) -> NoReturn:
        if not self.exists():
            raise CommandError(f"The tool {self.TOOL_NAME} is not present in your system")

    def alread_installed_message(self):
        return f"The tool {self.TOOL_NAME} is already installed"


class PackageManagementTool(ToolBase):
    def update(self) -> NoReturn:
        raise NotImplementedError()

    def install_qemu_kvm(self) -> NoReturn:
        raise NotImplementedError()

    def install_scream(self) -> NoReturn:
        raise NotImplementedError()

    def install_git(self) -> NoReturn:
        raise NotImplementedError()

    def install_build_essential(self) -> NoReturn:
        raise NotImplementedError()

    def configure_user_access(self) -> NoReturn:
        self.execute_as_super(["sudo", "usermod", "-aG", "libvirt,libvirtd,kvm", getuser()])

    def enable_virtd(self) -> NoReturn:
        self.execute_application(["sudo", "systemctl", "enable", "libvirtd.service"])
        self.execute_application(["sudo", "systemctl", "start", "libvirtd.service"])

    def virtd_check_status(self) -> NoReturn:
        self.execute_application(["sudo", "systemctl", "--no-pager", "status", "libvirtd.service"])


class PacmanTool(PackageManagementTool):
    TOOL_NAME = "pacman"

    def update(self) -> NoReturn:
        self.execute_as_super(["-Syy"])

    def install_qemu_kvm(self) -> NoReturn:
        self.update()
        self.execute_as_super(["-S", "qemu", "virt-manager", "virt-viewer", "dnsmasq", "vde2", "bridge-utils", "openbsd-netcat"])
        self.execute_as_super(["-S", "ebtables", "iptables"])
        self.enable_virtd()
        self.configure_user_access()
        self.virtd_check_status()

    def install_scream(self) -> NoReturn:
        clone_dirpath = GitTool().clone('https://aur.archlinux.org/scream.git', 'scream')
        self.execute_application(['makepkg'], cwd=clone_dirpath)

        binary_path = os.path.join(clone_dirpath, "pkg/scream/usr/bin/scream")
        self.execute_application(['sudo', 'cp', binary_path, "/usr/bin/scream"])

        scream_service_path = Path.expanduser("~/.config/systemd/user/scream-ivshmem-pulse.service")
        with open(scream_service_path, "w") as fp:
            fp.writelines([
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
            ])
        self.execute_application(["systemctl", "enable", "--user", "scream-ivshmem-pulse"])
        self.execute_application(["systemctl", "start", "--user", "scream-ivshmem-pulse"])

    def install_build_essential(self) -> NoReturn:
        self.update()
        self.execute_as_super(["-S", "base-devel"])

    def install_git(self) -> NoReturn:
        self.update()
        self.execute_as_super(["-S", "git"])


class AptGetTool(PackageManagementTool):
    TOOL_NAME = "apt-get"

    def update(self) -> NoReturn:
        self.execute_as_super(["update"])

    def install_qemu_kvm(self) -> NoReturn:
        self.update()
        self.execute_as_super(["qemu-kvm", "libvirt-daemon-system", "libvirt-clients", "bridge-utils"])
        self.enable_virtd()
        self.configure_user_access()
        self.virtd_check_status()


class IpTool(ToolBase):
    TOOL_NAME = "ip"
    DO_NOTHING_PARAMETER = "-V"


class EmulatorTool(ToolBase):
    TOOL_NAME = "qemu-system-x86_64"
    DO_NOTHING_PARAMETER = "-version"

    def install(self, show_message: bool = True) -> NoReturn:
        if self.exists(show_message):
            return
        PackageTool().install_qemu_kvm()


class IpTablesTool(ToolBase):
    TOOL_NAME = "iptables"


class GitTool(ToolBase):
    TOOL_NAME = "git"

    def install(self, show_message: bool = True):
        if self.exists(False):
            return
        PackageTool().install_git()
        if not self.exists(False):
            raise CommandError("Could not install git tool")

    def clone(self, url: str, dir_name: str) -> str:
        if not self.exists():
            PackageTool().install_git()
        if not self.exists():
            raise CommandError("The git tool is required to install scream.")
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)
        clone_path = os.path.join(TEMP_DIR, dir_name)
        self.execute(['clone', url, clone_path])
        return clone_path


PackageTool = PacmanTool if PacmanTool().exists() else AptGetTool
