from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Iterator, List

AUDIO_VIDEO_VENDORS_RE = ({"audio": "NVIDIA Corporation", "video": "NVIDIA Corporation.*GeForce"},)
DEVICE_INFO_RE = "([0-9]{2}:[0-9]{2}\\.[0-9])[^:]*:(.*)\\[([0-9a-f]{4}):([0-9a-f]{4})\\].*"  # parse a string like: 01:00.0 VGA compatible controller [0300]: NVIDIA Corporation GP104 [GeForce GTX 1080] [10de:1b80] (rev a1)


class GPU:
    def __init__(self, video_vendor: str, audio_vendor: str, video_address: str, audio_address: str) -> None:
        self._video_vendor = video_vendor
        self._audio_vendor = audio_vendor
        self._video_address = video_address
        self._audio_address = audio_address

    @property
    def video_vendor(self) -> str:
        return self._video_vendor

    @property
    def audio_vendor(self) -> str:
        return self._audio_vendor

    @property
    def audio_address(self) -> str:
        return self._audio_address

    @property
    def video_address(self) -> str:
        return self._video_address

    @classmethod
    def from_vendor(cls, vendor_devices: Dict) -> GPU:
        device_re = re.compile(DEVICE_INFO_RE)
        video_match = device_re.match(vendor_devices["video"])
        audio_match = device_re.match(vendor_devices["audio"])
        if not video_match:
            raise Exception("Invalid vendor device information GPU not found")
        audio_vendor = ""
        video_vendor = ""
        audio_address = ""
        video_address = ""
        if audio_match:
            audio_vendor = audio_match.group(2).strip()
            audio_address = f"0000:{audio_match.group(1)}"
        video_vendor = video_match.group(2).strip()
        video_address = f"0000:{video_match.group(1)}"
        return cls(video_vendor, audio_vendor, video_address, audio_address)


def run_read_output(parameters: List[str], shell: bool = False) -> Iterator[str]:
    process = subprocess.Popen(list(parameters), stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, shell=shell)
    try:
        for output_line in iter(process.stdout.readline, ""):
            yield output_line.strip()
    finally:
        process.stdout.close()
        return_code = process.wait()
        if return_code:
            raise subprocess.CalledProcessError(return_code, str(parameters))


def get_IOMMU_information() -> List[str]:
    return list(run_read_output([
        "sh", "-c",
        "dmesg | grep -i -e DMAR -e IOMMU"
    ]))


def get_iommu_devices() -> Iterator[str]:
    base_dir = "/sys/kernel/iommu_groups/"
    for dir in os.listdir(base_dir):
        for device in os.listdir(f"{base_dir}/{dir}/devices"):
            for line in run_read_output(["lspci", "-nns", device]):
                yield line


def search_gpu_device(devices: List[str], vendor: Dict) -> Dict:
    audio = ""
    video = ""
    video_re = re.compile(vendor["video"])
    audio_re = re.compile(vendor["audio"])
    start_str = ""
    for device in devices:
        if "vga compatible controller" in device.lower():
            match = video_re.search(device)
            if match and (device.startswith(start_str) or not start_str):
                start_str = device[0:6]
                video = device

        if "audio device" in device.lower():
            match = audio_re.search(device)
            if match and (device.startswith(start_str) or not start_str):
                start_str = device[0:6]
                audio = device

    return {"video": video, "audio": audio}


def gpus_from_iommu_devices() -> List[GPU]:
    devices = list(get_iommu_devices())
    gpus = []
    for vendor in AUDIO_VIDEO_VENDORS_RE:
        vendor_lines = search_gpu_device(devices, vendor)
        if vendor_lines["video"]:
            gpus.append(GPU.from_vendor(vendor_lines))
            devices = [d for d in devices if d not in vendor_lines["video"] and d not in vendor_lines["audio"]]
    return gpus


def create_qcow_disk(disk_filepath: Path, disk_size: int) -> Iterator[str]:
    for line in run_read_output([
            "qemu-img", "create", "-f", "qcow2", str(disk_filepath), f"{disk_size}M"
    ]):
        yield line
