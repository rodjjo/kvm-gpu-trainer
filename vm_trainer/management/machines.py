import os
import random
import subprocess
from typing import Union
from uuid import uuid4

import click
import yaml

from .clickgroup import cli
from vm_trainer.components.network import TapNetwork
from vm_trainer.exceptions import CommandError
from vm_trainer.settings import VMS_DIR
from vm_trainer.utils import gpus_from_iommu_devices, create_qcow_disk
from vm_trainer.components.dependencies import DependencyManager
from vm_trainer.yamldoc import Dumper, Loader


# brctl addbr br0
# brctl addif br0 enp0s25
# ip tuntap add dev tap0 mode tap
# brctl addif br0 tap0
# ip link set up dev tap0
# ip addr add dev bridge_name 192.168.66.66/24
# If any of the bridged devices (e.g. eth0, tap0) had dhcpcd enabled, stop and disable the dhcpcd@eth0.service daemon. Or set IP=no to the netctl profiles.
# ip link set dev br0 address XX:XX:XX:XX:XX:XX  where xx:xx... is the mac address to the real interface

def get_random_mac():
    # qemu mac address
    return "52:54:%02x:%02x:%02x:%02x" % (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


def get_machine_settings_filepath(machine_name):
    if not os.path.exists(VMS_DIR):
        os.makedirs(VMS_DIR)
    filepath = os.path.join(VMS_DIR, f"{machine_name}.yaml")
    return filepath


def get_machine_domainkey_path(machine_name):
    return os.path.join(VMS_DIR, f"{machine_name}-key.aes")


def load_machine_settings(machine_name):
    filepath = get_machine_settings_filepath(machine_name)
    if not os.path.exists(filepath):
        raise CommandError(f'File not found: {filepath}')

    with open(filepath) as fp:
        return yaml.load(fp, Loader=Loader)


def get_machine_disk_filepath(machine_name):
    disk_dir = os.path.join(VMS_DIR, f"{machine_name}-disks")
    if not os.path.exists(disk_dir):
        os.makedirs(disk_dir)
    return os.path.join(disk_dir, f"{machine_name}.qcow")


def create_disk(machine_name):
    settings = load_machine_settings(machine_name)
    disk_filepath = get_machine_disk_filepath(machine_name)

    if os.path.exists(disk_filepath):
        raise CommandError(f'The machine disk already exists at {disk_filepath}')

    disk_size = settings["machine"]["disk-size"]
    if disk_size < 5000:
        raise CommandError('The machine configuration has a very small disk. Operation Aborted')

    for line in create_qcow_disk(disk_filepath, disk_size):
        click.echo(line)


def update_machine_setting(machine_name, setting_name, value):
    machine_settings = load_machine_settings(machine_name)
    machine_settings["machine"][setting_name] = value

    filepath = get_machine_settings_filepath(machine_name)
    with open(filepath, "w") as fp:
        yaml.dump(machine_settings, fp, Dumper=Dumper)


def get_machine_run_command_line(machine_name, iso_file=None):
    settings = load_machine_settings(machine_name)

    gpus = []
    pci_bus = {0: ("pci.4", "pci.5"), 1: ("pci.2", "pci.3")}
    for index, gpu in enumerate(settings["machine"]["gpus"]):
        if index > 1:
            click.echo("Currently able to configure two gpus")
            break
        gpus += [
            "-device", f"vfio-pci,host={gpu['video']['address']},id=hostdev0,bus={pci_bus[index][0]},addr=0x0",
            "-device", f"vfio-pci,host={gpu['audio']['address']},id=hostdev1,bus={pci_bus[index][1]},addr=0x0",
        ]

    # ivshmem-server -p /var/run/ivshmem-server.pid  -S /tmp/ivshmem_socket  -M ivshmem -m /dev/shm -l 1M -n 2
    shared_memories = []
    if os.path.exists("/dev/shm/scream-ivshmem"):
        shared_memories = ["-object", "memory-backend-file,id=shmmem-shmem0,mem-path=/dev/shm/scream-ivshmem,size=2097152,share=yes",
                           "-device", "ivshmem-plain,id=shmem0,memdev=shmmem-shmem0,bus=pci.11,addr=0x2"]

    if settings["machine"].get("custom-disk"):
        hda_disk_path = settings["machine"]["custom-disk"]
    else:
        hda_disk_path = get_machine_disk_filepath(machine_name)

    addtional_disk_devices = []
    for disk_number in range(1, 3):
        name = f"physical-disk{disk_number}"
        if name in settings["machine"]:
            device_name = settings["machine"][name]
            addtional_disk_devices += [
                "-blockdev", '{"driver":"host_device","filename":"%s","node-name":"libvirt-%s-storage","cache":{"direct":true,"no-flush":false},"auto-read-only":true,"discard":"unmap"}' % (
                    device_name, disk_number
                ),
                "-blockdev", '{"node-name":"libvirt-%s-format","read-only":false,"cache":{"direct":true,"no-flush":false},"driver":"raw","file":"libvirt-%s-storage"}' % (
                    disk_number, disk_number
                ),
                "-device", f"virtio-blk-pci,bus=pci.{6 + disk_number},addr=0x0,drive=libvirt-{disk_number}-format,id=virtio-disk2,write-cache=on",
            ]

    domainkey = []
    keypath = get_machine_domainkey_path(machine_name)
    if os.path.exists(keypath):
        domainkey = [
            "-object", f"secret,id=masterKey0,format=raw,file={keypath}"
        ]

    dvd_driver = []
    if iso_file and os.path.exists(iso_file):
        dvd_driver = [
            "-blockdev", '{"driver":"file","filename":"%s","node-name":"libvirt-2-storage","auto-read-only":true,"discard":"unmap"}' % iso_file,
            "-blockdev", '{"node-name":"libvirt-2-format","read-only":true,"driver":"raw","file":"libvirt-2-storage"}',
            "-device", "ide-cd,bus=ide.1,drive=libvirt-2-format,id=sata0-0-1",
        ]

    command_line = [
        "sudo",
        "qemu-system-x86_64",
        "-name", f"guest={machine_name},debug-threads=on"] + domainkey + [
        "-machine", 'pc-q35-5.1,accel=kvm,usb=off,vmport=off,dump-guest-core=off,kernel_irqchip=on',
        "-bios", "/usr/share/edk2-ovmf/x64/OVMF_CODE.fd",
        "-cpu", "host,migratable=on,hv-time,hv-relaxed,hv-vapic,hv-spinlocks=0x4000,hv-vpindex,hv-runtime,hv-synic,hv-stimer,hv-reset,hv-vendor-id=441863197303,hv-frequencies,hv-reenlightenment,hv-tlbflush,kvm=off",
        "-m", str((settings["machine"]["memory"] // 4) * 4),
        "-overcommit",
        "mem-lock=off",
        "-smp", "4,sockets=1,dies=1,cores=4,threads=1",
        "-uuid", settings["machine"]["uuid"],
        "-no-user-config",
        "-nodefaults",
        "-rtc", "base=localtime,driftfix=slew",
        "-global", "kvm-pit.lost_tick_policy=delay",
        "-no-hpet",
        "-global", "ICH9-LPC.disable_s3=1",
        "-global", "ICH9-LPC.disable_s4=1",
        # -serial mon:stdio -append 'console=ttyS0'   # for serial redirection
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
        "-blockdev", '{"driver":"file","filename":"%s","node-name":"libvirt-3-storage","auto-read-only":true,"discard":"unmap"}' % hda_disk_path,
        "-blockdev", '{"node-name":"libvirt-3-format","read-only":false,"driver":"qcow2","file":"libvirt-3-storage","backing":null}',
        "-device", "ide-hd,bus=ide.0,drive=libvirt-3-format,id=sata0-0-0,bootindex=1",
    ] + gpus + dvd_driver + shared_memories + addtional_disk_devices + [
        "-netdev", f"tap,id=hostnet0,ifname={TapNetwork.TAP_INTERFACE_NAME},script=no,downscript=no",  # tap,fd=32,id=hostnet0
        "-device", f"e1000e,netdev=hostnet0,id=net0,mac={settings['machine']['mac-address']},bus=pci.6,addr=0x0",
        # "-device", "qxl-vga,id=video0,ram_size=67108864,vram_size=67108864,vram64_size_mb=0,vgamem_mb=16,max_outputs=1,bus=pcie.0,addr=0x7",
        "-nographic",
        "-sandbox", "on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny",
        "-msg", "timestamp=on",
        "-object", "input-linux,id=mouse1,evdev=/dev/input/by-id/usb-HP_HP_Wireless_Keyboard_Combo_200-event-mouse",  # share host keyboard
        "-object", "input-linux,id=kbd1,evdev=/dev/input/by-id/usb-SIGMACHIP_USB_Keyboard-event-kbd,grab_all=on,repeat=on",  # share host mouse
    ]
    return command_line


def run_machine(machine_name, iso_file=None):
    command_line = get_machine_run_command_line(machine_name, iso_file)
    subprocess.check_call(command_line)


def setup_machine(machine_name, iso_file):
    pass


@cli.command(help="Create new machine settings")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--cpus", default="-1", type=int, help="Number of cpu cores (default = -1 all cores)")
@click.option("--disk-size", required=False, type=int, help="Disk space in MB")
@click.option("--existing-disk", required=False, type=str, help="Use an existing disk")
@click.option("--memory", required=True, type=int, help="Amount of memory in MB")
def machine_create(name: str, cpus: int, memory: int, existing_disk: Union[str, None], disk_size: Union[int, None]):
    DependencyManager.check_all()
    filepath = get_machine_settings_filepath(name)
    if os.path.exists(filepath):
        raise CommandError(f"The VM {name} already exists. File: {filepath}")

    if cpus < -1:
        raise CommandError("Invalid cpu count")

    if not existing_disk and not disk_size:
        raise CommandError('You must specify an existing-disk or the disk-size parameter')

    if not existing_disk and disk_size < 5000:
        raise CommandError("Disk size too small. Expected 5000 or more")

    if memory < 256:
        raise CommandError("Memory too small. Expected 256 or more")

    machine = {
        "machine": {
            "uuid": str(uuid4()),
            "mac-address": get_random_mac(),
            "name": name,
            "cpus": cpus,
            "memory": memory,
            "disk-size": disk_size,
            "custom-disk": existing_disk,
        }
    }
    with open(filepath, "w") as fp:
        yaml.dump(machine, fp, Dumper=Dumper)

    if not existing_disk:
        create_disk(name)


@cli.command(help="Change the number of cpu cores used by an existing machine")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--cpus", default="-1", type=int, help="Number of cpu cores (default = -1 all cores)")
def machine_set_cpus(name, cpus):
    DependencyManager.check_all()
    update_machine_setting(name, "cpus", cpus)


@cli.command(help="Change the amount of memory RAM of an existing machine")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--memory", required=True, type=int, help="Amount of memory in MB")
def machine_set_memory(name, memory):
    DependencyManager.check_all()
    update_machine_setting(name, "memory", memory)


@cli.command(help="List existing machine names")
def machine_list():
    for name in os.listdir(VMS_DIR):
        if not name.endswith('.yaml'):
            continue
        click.echo(name[0:-5])


@cli.command(help="Assign gpu's to an existing machine")
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_set_gpus(name):
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
    update_machine_setting(name, "gpus", data)


@cli.command(help='Create the virtual machine disk (qcow)')
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_create_disk(name):
    create_disk(name)


@cli.command(help="Add a physical disk device to the machine")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--device", required=True, help="The disk device to map into the machine")
def machine_set_disk_device(name, device):
    update_machine_setting(name, "physical-disk1", device)


@cli.command(help="Run the machine with an iso attached on it")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--iso", required=True, help="The path to the iso file to attach")
def machine_run_with_iso(name, iso):
    iso = os.path.abspath(iso)
    if not os.path.exists(iso):
        raise CommandError(f"File not found: {iso}")
    run_machine(name, iso)


@cli.command(help="Run the machine")
@click.option("--name", required=True, help="The name of the virtual machine")
def machine_run(name):
    run_machine(name)
