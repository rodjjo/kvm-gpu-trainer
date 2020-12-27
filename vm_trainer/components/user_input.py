import os
from typing import Iterator


def is_input_event_device(device: str) -> bool:
    device = device.lower()
    if 'event' in device:
        return 'mouse' in device or 'keyboard' in device
    return False


class UserInput:
    INPUT_DEVICES_DIRECTORY = '/dev/input/by-id/'

    @staticmethod
    def list_devices() -> Iterator[str]:
        for input_device in os.listdir(UserInput.INPUT_DEVICES_DIRECTORY):
            if is_input_event_device(input_device.lower()):
                yield input_device

    @staticmethod
    def list_mouses() -> Iterator[str]:
        for input_device in UserInput.list_devices():
            if 'mouse' in input_device.lower():
                yield input_device

    @staticmethod
    def list_keyboards() -> Iterator[str]:
        for input_device in UserInput.list_devices():
            if 'keyboard' in input_device.lower() and 'mouse' not in input_device.lower():
                yield input_device
