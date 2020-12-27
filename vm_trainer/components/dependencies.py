import os
import platform
import subprocess
from typing import List, Tuple

from vm_trainer.exceptions import CommandError

from .tools import EmulatorTool, IpTablesTool, IpTool

StringList = List[str]
ToolChecklist = List[Tuple[str, str, str]]
PathChecklist = List[Tuple[str, str]]


class DependencyManager:
    COMPATIBLE_DISTROS = ('archlinux',)
    EMULATOR_TOOL = EmulatorTool.TOOL_NAME
    IP_TOOL = IpTool.TOOL_NAME
    IP_TABLES_TOOL = IpTablesTool.TOOL_NAME
    IOMMU_GROUPS_DIRPATH = "/sys/kernel/iommu_groups"
    OVMF_BIOS_FILEPATH = "/usr/share/edk2-ovmf/x64/OVMF_CODE.fd"

    @staticmethod
    def is_compatible_distro() -> bool:
        system_version = platform.release()
        return "arch2" in system_version or "ubuntu" in system_version

    @staticmethod
    def is_processor_compatible() -> bool:
        count = 0
        with open("/proc/cpuinfo", "r") as fp:
            for line in fp.readlines():
                if 'vmx' in line or 'svm' in line:
                    count += 1
        return count != 0

    @staticmethod
    def has_kvm_device() -> bool:
        return os.path.exists("/dev/kvm")

    @staticmethod
    def have_tool(tool_name: str, do_nothing_parameter: str) -> bool:
        try:
            subprocess.check_call([tool_name, do_nothing_parameter])
            return True
        except FileNotFoundError:
            pass
        return False

    @staticmethod
    def get_tool_list() -> ToolChecklist:
        not_found_msg = "is not present in your system."
        return [
            (DependencyManager.EMULATOR_TOOL, "-version", f"{DependencyManager.EMULATOR_TOOL} {not_found_msg}"),
            (DependencyManager.IP_TOOL, "-V", f"The {DependencyManager.IP_TOOL} {not_found_msg}"),
            (DependencyManager.IP_TABLES_TOOL, "--version", f"The {DependencyManager.IP_TABLES_TOOL} {not_found_msg}"),
        ]

    @staticmethod
    def get_path_list() -> PathChecklist:
        not_found_msg = "was not found in you filesystem."
        return [
            (DependencyManager.IOMMU_GROUPS_DIRPATH, f"The directory '{DependencyManager.IOMMU_GROUPS_DIRPATH}' {not_found_msg}"),
            (DependencyManager.OVMF_BIOS_FILEPATH, f"The ovmf bios file '{DependencyManager.OVMF_BIOS_FILEPATH}' {not_found_msg}"),
        ]

    @staticmethod
    def check_all_tools() -> StringList:
        tool_errors = []
        tools = DependencyManager.get_tool_list()
        with open(os.devnull, 'w') as nullfp:
            for tool in tools:
                try:
                    subprocess.check_call([tool[0], tool[1]], stdout=nullfp)
                except FileNotFoundError:
                    tool_errors.append(tool[2])
        return tool_errors

    @staticmethod
    def check_all_paths() -> StringList:
        pathChecklist = DependencyManager.get_path_list()
        path_errors = []
        for path_item in pathChecklist:
            if not os.path.exists(path_item[0]):
                path_errors.append(path_item[1])
        return path_errors

    @staticmethod
    def check_all() -> None:
        if not DependencyManager.is_compatible_distro():
            raise CommandError("vm_trainer does not support your linux distribution (try using ubuntu or arch-linux)")
        if not DependencyManager.is_processor_compatible():
            raise CommandError("Your pocessor does not have virtualization capabilities")
        tool_errors = DependencyManager.check_all_tools()
        if not DependencyManager.has_kvm_device():
            tool_errors = ["Your system does not have kvm device /dev/kvm please install qemu and kvm"] + tool_errors
        path_errors = DependencyManager.check_all_paths()
        error_message = ""

        if tool_errors:
            error_message = "\n".join(tool_errors)

        if path_errors:
            error_message += "\n".join(path_errors)

        if error_message:
            raise CommandError(error_message)
