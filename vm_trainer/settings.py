import os
from pathlib import Path

import yaml


class Settings():
    def __init__(self) -> None:
        self._settings = {
            "network-ip": "192.168.66.1/24"
        }
        self.load()

    def settings_dir(self) -> Path:
        dirpath = Path.expanduser(Path("~/.vmtrainer"))
        if not dirpath.exists():
            os.makedirs(dirpath)
        return dirpath

    def tpm_dir(self) -> Path:
        dirpath = self.settings_dir().joinpath("tpm")
        if not dirpath.exists():
            os.makedirs(dirpath)
        return dirpath

    def tpm_socket_path(self) -> Path:
        return self.tpm_dir().joinpath("swtpm-sock.sock")


    def network_interface(self) -> str:
        return self._settings.get("network-interface", "")

    def qemu_binary_path(self) -> str:
        return self._settings.get("qemu-bin-path", "qemu-system-x86_64")

    def temp_dir(self) -> Path:
        dirpath = self.settings_dir().joinpath('temp')
        if not dirpath.exists():
            os.makedirs(dirpath)
        return dirpath

    def machines_dir(self) -> Path:
        dirpath = self.settings_dir().joinpath("machines")
        if not dirpath.exists():
            os.makedirs(dirpath)
        return dirpath

    def settings_path(self) -> Path:
        return self.settings_dir().joinpath("settings.yaml")

    def disk_directory(self) -> Path:
        if self._settings.get("disk-directory"):
            return Path(self._settings["disk-directory"])
        return self.machines_dir()

    def network_ip(self) -> str:
        return self._settings["network-ip"]

    def set_disk_directory(self, directory_path: str) -> None:
        self._settings["disk-directory"] = directory_path

    def set_network_ip(self, ip_address: str) -> None:
        self._settings["network-ip"] = ip_address

    def set_network_interface(self, name: str) -> None:
        self._settings["network-interface"] = name

    def set_qemu_binary_path(self, path: str) -> None:
        self._settings["qemu-bin-path"] = path

    def load(self) -> None:
        if not self.settings_path().exists():
            return
        with open(self.settings_path(), "r") as fp:
            self._settings = yaml.load(fp, Loader=yaml.Loader)

    def save(self) -> None:
        with open(self.settings_path(), "w") as fp:
            yaml.dump(self._settings, fp, Dumper=yaml.Dumper)
