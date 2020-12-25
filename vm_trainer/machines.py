import os
import random
import shutil
import subprocess
from uuid import uuid4

import click
import yaml

from .clickgroup import cli
from .exceptions import CommandError
from .settings import VMS_DIR
from .utils import check_compatible_device, gpus_from_iommu_devices, create_qcow_disk
from .yamldoc import Dumper, Loader


# brctl addbr br0
# brctl addif br0 enp0s25
# ip tuntap add dev tap0 mode tap
# brctl addif br0 tap0
# ip link set up dev tap0
# ip addr add dev bridge_name 192.168.66.66/24
# If any of the bridged devices (e.g. eth0, tap0) had dhcpcd enabled, stop and disable the dhcpcd@eth0.service daemon. Or set IP=no to the netctl profiles.
# ip link set dev br0 address XX:XX:XX:XX:XX:XX  where xx:xx... is the mac address to the real interface

def get_random_mac():
    # locally administered unicast address
    return "02:00:00:%02x:%02x:%02x" % (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))


def get_machine_settings_filepath(machine_name):
    if not os.path.exists(VMS_DIR):
        os.makedirs(VMS_DIR)
    filepath = os.path.join(VMS_DIR, f"{machine_name}.yaml")
    return filepath


def get_nvram_filepath(machine_name):
    nvram_dir = os.path.join(VMS_DIR, "nvram")
    if not os.path.exists(nvram_dir):
        os.makedirs(nvram_dir)
    filepath = os.path.join(nvram_dir, f"nvram-{machine_name}-vars.fd")
    if not os.path.exists(filepath):
        shutil.copy("/usr/share/edk2-ovmf/x64/OVMF_CODE.fd", filepath)
    return filepath


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


def check_device():
    error = check_compatible_device()
    if error:
        raise CommandError(error)


def get_machine_run_command_line(machine_name, iso_file=None):
    settings = load_machine_settings(machine_name)

    gpus = []
    pci_bus = {0: ("pci.5", "pci.6"), 1: ("pci.2", "pci.3")}
    for index, gpu in enumerate(settings["machine"]["gpus"]):
        if index > 1:
            click.echo("Currently able to configure two gpus")
            break
        gpus += [
            "-device", f"vfio-pci,host={gpu['video']['address']},id=hostdev0,bus={pci_bus[index][0]},addr=0x0",
            "-device", f"vfio-pci,host={gpu['audio']['address']},id=hostdev1,bus={pci_bus[index][1]},addr=0x0",
        ]

    # shared_memories = []
    # if os.path.exists("/dev/shm/scream-ivshmem"):
    #    shared_memories = ["-object", "memory-backend-file,id=shmmem-shmem0,mem-path=/dev/shm/scream-ivshmem,size=2097152,share=yes"
    #                       "-device", "ivshmem-plain,id=shmem0,memdev=shmmem-shmem0,bus=pci.8,addr=0x2"]

    dvd_driver = []
    if iso_file and os.path.exists(iso_file):
        click.echo(iso_file)
        dvd_driver = [
            "-boot", "d",
            "-cdrom", str(iso_file),
        ]
        # dvd_driver = [
        #    "-blockdev", '{"driver":"file","filename":"%s","node-name":"libvirt-2-storage","auto-read-only":true,"discard":"unmap"}' % iso_file,
        #    "-blockdev", '{"node-name":"libvirt-2-format","read-only":true,"driver":"raw","file":"libvirt-2-storage"}',
        #    "-device", "ide-cd,bus=ide.1,drive=libvirt-2-format,id=sata0-0-1",
        # ]

    command_line = [
        "sudo",
        "qemu-system-x86_64",
        "-name", f"guest={machine_name},debug-threads=on",
        # "-S",
        # "-object", "secret,id=masterKey0,format=raw,file=/var/lib/libvirt/qemu/domain-1-win10-2/master-key.aes"
        # "-blockdev", '{"driver":"file","filename":"/usr/share/edk2-ovmf/x64/OVMF_CODE.fd","node-name":"libvirt-pflash0-storage","auto-read-only":true,"discard":"unmap"}',
        # "-blockdev", '{"node-name":"libvirt-pflash0-format","read-only":true,"driver":"raw","file":"libvirt-pflash0-storage"}',
        # "-blockdev", '{"driver":"file","filename":"%s","node-name":"libvirt-pflash1-storage","auto-read-only":true,"discard":"unmap"}' % get_nvram_filepath(machine_name),
        # "-blockdev", '{"node-name":"libvirt-pflash1-format","read-only":false,"driver":"raw","file":"libvirt-pflash1-storage"}',
        "-machine", 'pc-q35-5.1,accel=kvm,usb=off,vmport=off,dump-guest-core=off,kernel_irqchip=on',
        "-bios", os.path.join(VMS_DIR, "bios.bin"),
        # "-machine", 'pc-q35-5.1,accel=kvm,usb=off,vmport=off,dump-guest-core=off,kernel_irqchip=on,pflash0=libvirt-pflash0-format,pflash1=libvirt-pflash1-format',
        "-cpu", "host,migratable=on,hv-time,hv-relaxed,hv-vapic,hv-spinlocks=0x4000,hv-vpindex,hv-runtime,hv-synic,hv-stimer,hv-reset,hv-vendor-id=441863197303,hv-frequencies,hv-reenlightenment,hv-tlbflush,kvm=off",
        "-m", str((settings["machine"]["memory"] // 4) * 4),
        "-overcommit",
        "mem-lock=off",
        "-smp", "4,sockets=1,dies=1,cores=4,threads=1",
        "-uuid", settings["machine"]["uuid"],
        "-no-user-config",
        "-nodefaults",
        # "-chardev", "socket,id=charmonitor,fd=30,server,nowait",
        # "-mon", "chardev=charmonitor,id=monitor,mode=control",
        "-rtc", "base=localtime,driftfix=slew",
        "-global", "kvm-pit.lost_tick_policy=delay",
        "-no-hpet",
        # "-no-shutdown",
        "-global", "ICH9-LPC.disable_s3=1",
        "-global", "ICH9-LPC.disable_s4=1",
        # "-boot", "strict=on",
        "-device", "pcie-root-port,port=0x10,chassis=1,id=pci.1,bus=pcie.0,multifunction=on,addr=0x2",
        "-device", "pcie-root-port,port=0x11,chassis=2,id=pci.2,bus=pcie.0,addr=0x2.0x1",
        "-device", "pcie-root-port,port=0x12,chassis=3,id=pci.3,bus=pcie.0,addr=0x2.0x2",
        "-device", "pcie-root-port,port=0x13,chassis=4,id=pci.4,bus=pcie.0,addr=0x2.0x3",
        "-device", "pcie-root-port,port=0x14,chassis=5,id=pci.5,bus=pcie.0,addr=0x2.0x4",
        "-device", "pcie-root-port,port=0x15,chassis=6,id=pci.6,bus=pcie.0,addr=0x2.0x5",
        "-device", "pcie-root-port,port=0x16,chassis=7,id=pci.7,bus=pcie.0,addr=0x2.0x6",
        "-device", "pcie-root-port,port=0x17,chassis=9,id=pci.9,bus=pcie.0,addr=0x2.0x7",
        "-device", "pcie-pci-bridge,id=pci.8,bus=pci.1,addr=0x0",
        "-hda", get_machine_disk_filepath(machine_name),
        # "-blockdev", '{"driver":"file","filename":"%s","node-name":"libvirt-3-storage","auto-read-only":true,"discard":"unmap"}' % get_machine_disk_filepath(machine_name),
        # "-blockdev", '{"node-name":"libvirt-3-format","read-only":false,"driver":"qcow2","file":"libvirt-3-storage","backing":null}',
        # "-device", "ide-hd,bus=ide.0,drive=libvirt-3-format,id=sata0-0-0,bootindex=1",
    ] + gpus + dvd_driver + [
        # -blockdev {"driver":"host_device","filename":"/dev/sda","node-name":"libvirt-1-storage","cache":{"direct":true,"no-flush":false},"auto-read-only":true,"discard":"unmap"}
        # "-blockdev", '{"node-name":"libvirt-1-format","read-only":false,"cache":{"direct":true,"no-flush":false},"driver":"raw","file":"libvirt-1-storage"}',
        # "-device", "virtio-blk-pci,bus=pci.10,addr=0x0,drive=libvirt-1-format,id=virtio-disk2,write-cache=on",
        "-netdev", "tap,id=hostnet0,ifname=tap0,script=no,downscript=no",  # tap,fd=32,id=hostnet0
        "-device", f"e1000e,netdev=hostnet0,id=net0,mac={settings['machine']['mac-address']},bus=pci.7,addr=0x0",
        # "-chardev", "pty,id=charserial0",
        # "-device", "isa-serial,chardev=charserial0,id=serial0",
        # "-chardev", "spicevmc,id=charchannel0,name=vdagent",
        # "-device", "virtserialport,bus=virtio-serial0.0,nr=1,chardev=charchannel0,id=channel0,name=com.redhat.spice.0",
        # "-device", "usb-tablet,id=input0,bus=usb.0,port=1",
        # "-device", "virtio-keyboard-pci,id=input1,bus=pci.9,addr=0x0",
        # "-device", "usb-mouse,id=input2,bus=usb.0,port=4",
        # "-spice", "port=5900,addr=127.0.0.1,disable-ticketing,image-compression=off,seamless-migration=on",
        "-device", "qxl-vga,id=video0,ram_size=67108864,vram_size=67108864,vram64_size_mb=0,vgamem_mb=16,max_outputs=1,bus=pcie.0,addr=0x1",
        # "-display", "sdl",
        # "-display", "gtk,gl=on",
        # "-chardev", "spicevmc,id=charredir0,name=usbredir",
        # "-device", "usb-redir,chardev=charredir0,id=redir0,bus=usb.0,port=2",
        # "-chardev", "spicevmc,id=charredir1,name=usbredir",
        # "-device", "usb-redir,chardev=charredir1,id=redir1,bus=usb.0,port=3"
        # "-device", "virtio-balloon-pci,id=balloon0,bus=pci.4,addr=0x0",
        # "-sandbox", "on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny"] + shared_memories + [
        "-msg", "timestamp=on",
        # "-object", "input-linux,id=mouse1,evdev=/dev/input/by-id/usb-HP_HP_Wireless_Keyboard_Combo_200-event-mouse",  # share host keyboard
        # "-object", "input-linux,id=kbd1,evdev=/dev/input/by-id/usb-SIGMACHIP_USB_Keyboard-event-kbd,grab_all=on,repeat=on",  # share host mouse
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
@click.option("--disk-size", required=True, type=int, help="Disk space in MB")
@click.option("--memory", required=True, type=int, help="Amount of memory in MB")
def machine_create(name: str, cpus: int, memory: int, disk_size: int):
    check_device()
    filepath = get_machine_settings_filepath(name)
    if os.path.exists(filepath):
        raise CommandError(f"The VM {name} already exists. File: {filepath}")

    if cpus < -1:
        raise CommandError("Invalid cpu count")

    if disk_size < 5000:
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
            "disk-size": disk_size
        }
    }
    with open(filepath, "w") as fp:
        yaml.dump(machine, fp, Dumper=Dumper)

    create_disk(name)


@cli.command(help="Change the number of cpu cores used by an existing machine")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--cpus", default="-1", type=int, help="Number of cpu cores (default = -1 all cores)")
def machine_set_cpus(name, cpus):
    check_device()
    update_machine_setting(name, "cpus", cpus)


@cli.command(help="Change the amount of memory RAM of an existing machine")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--memory", required=True, type=int, help="Amount of memory in MB")
def machine_set_memory(name, memory):
    check_device()
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


@cli.command(help="Run the machine with an iso attached on it")
@click.option("--name", required=True, help="The name of the virtual machine")
@click.option("--iso", required=True, help="The path to the iso file to attach")
def machine_run_with_iso(name, iso):
    iso = os.path.abspath(iso)
    if not os.path.exists(iso):
        raise CommandError(f"File not found: {iso}")
    run_machine(name, iso)
