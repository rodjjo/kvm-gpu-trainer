# Virtual Gamming Machine

**GPU Passthroung for Gaming or Train models inside a virtual machine with GPU passthrough  (WIP)**

This project intend to create, modify and run virtual machines with GPU passthrough.  
Based in the tutorial: [PCI_passthrough_via_OVMF](https://wiki.archlinux.org/index.php/PCI_passthrough_via_OVMF)

## Attention

For while it intend to be supported by arch-linux host only.  
Early development state project (WIP).  

## TODO List
* Complete code type hints
* Turn possible use of setuptools
* Allow use of non root user launch the virtual machine.
* Add ubuntu support.
* Enable dhcp on the bridge network.
* Add looking glass support.

## Prepare the machine

Before you use this software:  
* Must have arch-linux installed
* You need to enable the virtualization tecnologies on your bios. ("VT-d" or "AMD-Vi" or Virtualization technology)  
* You need to enable the internal graphics and disable gpu startup on your bios.  
* You need to enable IOMMU using kernel parameters (modifying your boot loader menu or it's configuration file).  
  Set intel_iommu=on (for intel processors) or amd_iommu=on (for amd ones).  
  You can add iommu=pt to prevent linux from touching devices that cant pass through.  
  More information here [Edit kernel parameters](https://wiki.archlinux.org/index.php/Kernel_parameters)


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
