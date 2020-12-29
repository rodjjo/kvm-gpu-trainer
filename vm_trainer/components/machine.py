import os
import random
from pathlib import Path
from typing import List, Union
from uuid import uuid4

import click
import yaml

from vm_trainer.components.network import TapNetwork
from vm_trainer.components.tools import EmulatorTool
from vm_trainer.components.user_input import UserInput
from vm_trainer.exceptions import CommandError
from vm_trainer.settings import Settings
from vm_trainer.utils import create_qcow_disk, gpus_from_iommu_devices


def get_random_mac():
    random_sufix = (
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255),
        random.randint(0, 255)
    )
    return "52:54:%02x:%02x:%02x:%02x" % random_sufix


def select_something(message: str, options: List[str]) -> int:
    for index, text in enumerate(options):
        click.echo(f"{index} - {text}")
    answer = input(message)
    if answer not in [str(i) for i in range(len(options))]:
        raise CommandError("The option {answer} is not a valid one")
    return int(answer)


class Machine(object):
    BIOS_PATH = "/usr/share/edk2-ovmf/x64/OVMF_CODE.fd"

    def __init__(self, name: str) -> None:
        self._name = name
        self._settings = {
            "uuid": str(uuid4()),
            "mac-address": get_random_mac(),
            "name": name,
            "cpus": 1,
            "memory": 512,
            "disk-size": 20000,
            "custom-disk": None,
        }
        if self.exists():
            self.load_settings()

    def exists(self) -> bool:
        return self.config_path().exists()

    def must_exists(self) -> None:
        if not self.exists():
            raise CommandError(f"The Machine {self._name} does not exist")

    def load_settings(self) -> None:
        if self.config_path().exists():
            with open(self.config_path(), "r") as fp:
                self._settings = yaml.load(fp, Loader=yaml.Loader)["machine"]

    def config_path(self) -> Path:
        settings = Settings()
        return settings.machines_dir().joinpath(f"{self._name}.yaml")

    def save(self) -> None:
        with open(self.config_path(), "w") as fp:
            yaml.dump({"machine": self._settings}, fp, Dumper=yaml.Dumper)

    def check_requirements(self) -> None:
        self.must_exists()
        self.bios_must_exists()
        self.inputs_must_exists()
        self.disk_must_exists()
        self.raw_disk_must_exists()
        self.gpu_must_exists()

    def bios_must_exists(self) -> None:
        if not os.path.exists(self.BIOS_PATH):
            raise CommandError(f"Bios file not found: {self.BIOS_PATH}")

    def inputs_must_exists(self) -> None:
        if not self._settings.get("evdev-keyboard"):
            raise CommandError("The keyboard is not configured")
        if not self._settings.get("evdev-mouse"):
            raise CommandError("The mouse is not configured")

    def gpu_must_exists(self) -> None:
        if not self._settings.get("gpus"):
            raise CommandError("No gpu was specified to this machine. This project intend to use at least one gpu.")

    def disk_must_exists(self) -> None:
        if self._settings.get("disk-path"):
            if not os.path.exists(self._settings["disk-path"]):
                raise CommandError(f"File not found: {self._settings['disk-path']}")
        elif not self.get_disk_path().exists():
            raise CommandError(f"File not found: {self.get_disk_path()}")

    def raw_disk_must_exists(self) -> None:
        if self._settings.get("raw-disk1"):
            if os.path.exists(self._settings["raw-disk1"]):
                return CommandError(f"Disk device not found: {self._settings['raw-disk1']}")

    def exec_parameters_pci_slots(self) -> List[str]:
        return [
            "-device", "pcie-root-port,port=0x10,chassis=1,id=pci.1,bus=pcie.0,multifunction=on,addr=0x2",
            "-device", "pcie-root-port,port=0x11,chassis=2,id=pci.2,bus=pcie.0,addr=0x2.0x1",
            "-device", "pcie-root-port,port=0x12,chassis=3,id=pci.3,bus=pcie.0,addr=0x2.0x2",
            "-device", "pcie-root-port,port=0x13,chassis=4,id=pci.4,bus=pcie.0,addr=0x2.0x3",
            "-device", "pcie-root-port,port=0x14,chassis=5,id=pci.5,bus=pcie.0,addr=0x2.0x4",
            "-device", "pcie-root-port,port=0x15,chassis=6,id=pci.6,bus=pcie.0,addr=0x2.0x5",
            "-device", "pcie-root-port,port=0x16,chassis=7,id=pci.7,bus=pcie.0,addr=0x2.0x6",
            "-device", "pcie-root-port,port=0x17,chassis=8,id=pci.8,bus=pcie.0,addr=0x2.0x7",
            "-device", "pcie-root-port,port=0x18,chassis=9,id=pci.9,bus=pcie.0,addr=0x3.0x1",
            "-device", "pcie-root-port,port=0x19,chassis=10,id=pci.10,bus=pcie.0,addr=0x3.0x2",
            "-device", "pcie-pci-bridge,id=pci.11,bus=pci.1,addr=0x0",
        ]

    def exec_parameters_inputs(self) -> List[str]:
        params = []
        if self._settings.get("evdev-mouse"):
            params += [
                "-object", f"input-linux,id=mouse1,evdev={self._settings['evdev-mouse']}",
            ]
        if self._settings.get("evdev-keyboard"):
            params += [
                "-object", f"input-linux,id=kbd1,evdev={self._settings['evdev-keyboard']},grab_all=on,repeat=on",
            ]
        return params

    def exec_parameters_gpus(self) -> List[str]:
        params = []
        pci_bus = {0: ("pci.4", "pci.5"), 1: ("pci.2", "pci.3")}
        for index, gpu in enumerate(self._settings["gpus"]):
            if index > 1:
                click.echo("Currently able to configure two gpus")
                break
            params += [
                "-device", f"vfio-pci,host={gpu['video']['address']},id=hostdev0,bus={pci_bus[index][0]},addr=0x0",
                "-device", f"vfio-pci,host={gpu['audio']['address']},id=hostdev1,bus={pci_bus[index][1]},addr=0x0",
            ]
        return params

    def exec_parameters_disks(self) -> List[str]:
        disk_path = self.get_disk_path()
        params = [
            "-blockdev", '{"driver":"file","filename":"%s","node-name":"libvirt-3-storage","auto-read-only":true,"discard":"unmap"}' % disk_path,
            "-blockdev", '{"node-name":"libvirt-3-format","read-only":false,"driver":"qcow2","file":"libvirt-3-storage","backing":null}',
            "-device", "ide-hd,bus=ide.0,drive=libvirt-3-format,id=sata0-0-0,bootindex=1",
        ]
        for disk_number in range(1, 3):
            name = f"raw-disk{disk_number}"
            if name in self._settings:
                device_name = self._settings[name]
                params += [
                    "-blockdev", '{"driver":"host_device","filename":"%s","node-name":"libvirt-%s-storage","cache":{"direct":true,"no-flush":false},"auto-read-only":true,"discard":"unmap"}' % (
                        device_name, disk_number
                    ),
                    "-blockdev", '{"node-name":"libvirt-%s-format","read-only":false,"cache":{"direct":true,"no-flush":false},"driver":"raw","file":"libvirt-%s-storage"}' % (
                        disk_number, disk_number
                    ),
                    "-device", f"virtio-blk-pci,bus=pci.{6 + disk_number},addr=0x0,drive=libvirt-{disk_number}-format,id=virtio-disk2,write-cache=on",
                ]
        return params

    def exec_parameters_scream(self) -> List[str]:
        if os.path.exists("/dev/shm/scream-ivshmem"):
            return ["-object", "memory-backend-file,id=shmmem-shmem0,mem-path=/dev/shm/scream-ivshmem,size=2097152,share=yes",
                    "-device", "ivshmem-plain,id=shmem0,memdev=shmmem-shmem0,bus=pci.11,addr=0x2"]
        return []

    def exec_parameters_network(self) -> List[str]:
        return [
            "-netdev", f"tap,id=hostnet0,ifname={TapNetwork.TAP_INTERFACE_NAME},script=no,downscript=no",  # tap,fd=32,id=hostnet0
            "-device", f"e1000e,netdev=hostnet0,id=net0,mac={self._settings['mac-address']},bus=pci.6,addr=0x0",
        ]

    def exec_parameters_iso_disk(self, iso_path: str) -> List[str]:
        if not iso_path:
            return []

        abs_iso_path = os.path.abspath(iso_path)
        if not os.path.exists(abs_iso_path):
            raise CommandError(f"File not found: {abs_iso_path}")

        return [
            "-blockdev", '{"driver":"file","filename":"%s","node-name":"libvirt-2-storage","auto-read-only":true,"discard":"unmap"}' % abs_iso_path,
            "-blockdev", '{"node-name":"libvirt-2-format","read-only":true,"driver":"raw","file":"libvirt-2-storage"}',
            "-device", "ide-cd,bus=ide.1,drive=libvirt-2-format,id=sata0-0-1",
        ]

    def execute(self, iso_path: Union[str, None] = None) -> None:
        self.check_requirements()

        settings = Settings()
        if not settings.network_interface():
            raise CommandError("Target network not configured")

        TapNetwork.add_tap_network(settings.network_interface(), settings.network_ip())

        parameters = [
            "-name", f"guest={self._name},debug-threads=on",
            "-machine", 'pc-q35-5.1,accel=kvm,usb=off,vmport=off,dump-guest-core=off,kernel_irqchip=on',
            "-bios", self.BIOS_PATH,
            "-cpu", "host,migratable=on,hv-time,hv-relaxed,hv-vapic,hv-spinlocks=0x4000,hv-vpindex,hv-runtime,hv-synic,hv-stimer,hv-reset,hv-vendor-id=441863197303,hv-frequencies,hv-reenlightenment,hv-tlbflush,kvm=off",
            "-m", str((self._settings["memory"] // 4) * 4),
            "-overcommit",
            "mem-lock=off",
            "-smp", f"4,sockets=1,dies=1,cores={self._settings['cpus']},threads=1",
            "-uuid", self._settings["uuid"],
            "-no-user-config",
            "-nodefaults",
            "-rtc", "base=localtime,driftfix=slew",
            "-global", "kvm-pit.lost_tick_policy=delay",
            "-no-hpet",
            "-global", "ICH9-LPC.disable_s3=1",
            "-global", "ICH9-LPC.disable_s4=1",
            # -serial mon:stdio -append 'console=ttyS0'   # for serial redirection
            # "-device", "qxl-vga,id=video0,ram_size=67108864,vram_size=67108864,vram64_size_mb=0,vgamem_mb=16,max_outputs=1,bus=pcie.0,addr=0x7",
            "-nographic",
            "-sandbox", "on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny",
            "-msg", "timestamp=on",
        ]

        parameters += self.exec_parameters_pci_slots()
        parameters += self.exec_parameters_inputs()
        parameters += self.exec_parameters_disks()
        parameters += self.exec_parameters_scream()
        parameters += self.exec_parameters_gpus()
        parameters += self.exec_parameters_network()
        parameters += self.exec_parameters_iso_disk(iso_path)

        emulator = EmulatorTool()
        emulator.must_exists()
        emulator.execute_as_super(parameters)

    def set_cpus(self, cpu_count: int) -> None:
        if cpu_count < -1:
            raise CommandError("Invalid cpu count")
        self._settings["cpus"] = cpu_count

    def set_memory(self, memory_size: int) -> None:
        if memory_size < 256:
            raise CommandError("Memory too small. Expected 256 or more")
        self._settings["memory"] = memory_size

    def set_raw_disk(self, disk_path: str) -> None:
        if not os.path.exists(disk_path):
            raise CommandError(f"Disk not found: {disk_path}")
        self._settings["raw-disk1"] = disk_path

    def set_disk_path(self, disk_path: str) -> None:
        if not os.path.exists(disk_path):
            raise CommandError(f"Disk not found: {disk_path}")
        self._settings["disk-path"] = disk_path

    def set_disk_size(self, disk_size: int) -> None:
        if disk_size < 5000:
            raise CommandError("Disk too small. The value must be greater than 5000MB.")
        self._settings["disk-size"] = disk_size

    def raw_disk_present(self) -> bool:
        return "raw-disk1" in self._settings

    def get_disk_path(self) -> Path:
        if self._settings.get("disk-path"):
            if not Path(self._settings["disk-path"]).parent.exists():
                os.makedirs(Path(self._settings["disk-path"]).parent)
            return self._settings["disk-path"]
        settings = Settings()
        disk_dir = settings.disk_directory().joinpath(f"{self._name}-disks")
        if not os.path.exists(disk_dir):
            os.makedirs(disk_dir)
        return disk_dir.joinpath(f"{self._name}.qcow2")

    def create_disk(self) -> None:
        disk_filepath = self.get_disk_path()

        if disk_filepath.exists():
            raise CommandError(f'The machine disk already exists at {disk_filepath}')

        disk_size = self._settings["disk-size"]
        if disk_size < 5000:
            raise CommandError('The machine configuration has a very small disk. Operation Aborted')

        for line in create_qcow_disk(disk_filepath, disk_size):
            click.echo(line)

    def select_gpus(self) -> None:
        gpus = sorted(gpus_from_iommu_devices(), key=lambda gpu: gpu.video_vendor)
        if not gpus:
            raise CommandError("There is no GPU avaliable on this device")

        click.echo('Choose one or more gpu type the numbers separated by an comma:')

        for index, gpu in enumerate(gpus):
            click.echo(f"{index} - {gpu.video_vendor} video-address: [{gpu.video_address}]")

        user_input = input('Type the gpu numbers to use (comma separated):')

        if not user_input.strip():
            raise CommandError('No options were selected')

        selected_gpus = []
        indexes = set()
        for option in user_input.split(','):
            index = int(option)
            if index < 0 or index >= len(gpus):
                raise CommandError(f'{index} is not a valid option')
            if index in indexes:
                raise CommandError(f'The gpu number {index} is duplicated in your selection')
            indexes.add(index)
            selected_gpus.append(gpus[index])

        data = []
        for gpu in selected_gpus:
            item = {
                "video": {
                    "address": gpu.video_address,
                }
            }
            if gpu.audio_address:
                item["audio"] = {
                    "address": gpu.audio_address,
                }
            data.append(item)
        self._settings["gpus"] = data

    def select_mouse(self):
        mouses = list(UserInput.list_mouses())
        index = select_something("Type the mouse number from the options above:", mouses)
        self._settings['evdev-mouse'] = os.path.join(UserInput.INPUT_DEVICES_DIRECTORY, mouses[index])

    def select_keyboard(self):
        keyboards = list(UserInput.list_keyboards())
        index = select_something("Type the keyboard number from the options above:", keyboards)
        self._settings['evdev-keyboard'] = os.path.join(UserInput.INPUT_DEVICES_DIRECTORY, keyboards[index])
