# kvm-gpu-trainer


## Prepare the machine

Before you use this software:  
* You need to enable the virtualization tecnologies on your bios. ("VT-d" or "AMD-Vi" or Virtualization technology)  
* You need to enable the internal graphics and disable gpu startup on your bios.  
* You need to enable IOMMU using kernel parameters (modifying your boot loader menu or it's configuration file).  
  Set intel_iommu=on (for intel processors) or amd_iommu=on (for amd ones).  
  You can add iommu=pt to prevent linux from touching devices that cant pass through.  
  More information here [Edit kernel parameters](https://wiki.archlinux.org/index.php/Kernel_parameters)

## Verify the configurations

```bash

```