# Virtual Gamming Machine

**GPU Passthroung for Gaming or Train models inside a virtual machine with GPU passthrough  (WIP)**

This project intends to create, modify and run virtual machines with GPU passthrough.  
Based on the tutorial: [PCI_passthrough_via_OVMF](https://wiki.archlinux.org/index.php/PCI_passthrough_via_OVMF)

## Attention

**Early development state project (WIP).**  
Only Arch-Linux is supported currently. Ubuntu support is in development state.  

## TODO List
* Allow use of non root user launch the virtual machine.
* Add ubuntu support.
* Enable dhcp on the bridge network.
* Add [looking glass](https://github.com/gnif/LookingGlass) host installation support.

## Prepare the machine

Before you install/use this software:  
* Must have arch-linux installed
* You need to enable the virtualization tecnologies on your bios. ("VT-d" or "AMD-Vi" or Virtualization technology)  
* You need to enable the internal graphics and disable gpu startup on your bios.  
* You need to enable IOMMU using kernel parameters (modifying your boot loader menu or it's configuration file).  
  Set intel_iommu=on (for intel processors) or amd_iommu=on (for amd ones).  
  You can add iommu=pt to prevent linux from touching devices that cant pass through.  
  More information here [Edit kernel parameters](https://wiki.archlinux.org/index.php/Kernel_parameters)
* You need to have two monitor or a monitor with 2 inputs (for the virtual machine and the host).  

## Installation

```bash
pip3 install git+ssh://git@github.com/rodjjo/kvm-gpu-trainer.git --upgrade
```

## Show help

```bash
vm-trainer --help
# or vm-trainer <command> --help
```

## Install virtualization tools

```bash
vm-trainer depman-install-build-tools
vm-trainer depman-install-git
vm-trainer depman-install-qemu
```

## Install scream

For more informations about scream [click-here](https://github.com/duncanthrax/scream)
```bash
vm-trainer depman-install-scream
```

## Create the virtual machine

```bash
vm-trainer machine-create --name windows --cpus 4 --disk-size 200000 --memory 8192
```

## Show host available gpus

```bash
vm-trainer show-gpus
```
## Select the gpu for a machine

```bash
vm-trainer machine-set-gpus --name windows
```

## Select the keyboard

You can press both CTRL keys to switch between the virtual machine and the host
```bash
vm-trainer machine-select-keyboard --name windows
```

## Select the mouse

```bash
vm-trainer machine-select-mouse --name windows
```

## Configure the network (internet)

You have to define the physical network adapter connected to the internet.
```bash
vm-trainer network-show-physical
# example of outputs:
# eth0
# enp6s0
vm-trainer settings-set-network-interface --name eth0
```

## Run the virtual machine with an iso file to setup the operating system

```bash
vm-trainer machine-run-with-iso --name windows --iso location/to/my/original-windows10-disk.iso
```

## Run the virtual machine without an iso attached to it

After you installed the operating system
```bash
vm-trainer machine-run --name windows
```


## Network configuration

Currently, this project create a bridge network with the ip 192.168.66.1 (you can change this).  
You need to configure the network in the virtual machine to use static ip configuration:  
```text
IP: 192.168.66.2  
Gateway: 192.168.66.1  
DNS: 8.8.8.8  
```
DHCP (automatic ip configuration) support is at the TODO list.

## Configuring the audio inside the virtual machine

Take a look at [click-here](https://github.com/duncanthrax/scream)

## Tested on the system configuration

OS: Arch Linux  
Kernel: x86_64 Linux 5.8.9-arch2-1  
Shell: zsh 5.8  
Resolution: 1920x1080  
DE: GNOME 3.36.4  
Disk: 12T
CPU: Intel Core i5-3570 @ 4x 3.8GHz  
GPU: GeForce GTX 1080  
RAM: 24GB dual layer configuration: 8GB + 8GB and 4GB + 4GB  
