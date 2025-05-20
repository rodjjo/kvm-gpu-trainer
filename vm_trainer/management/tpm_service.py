import click
import os
from subprocess import check_call

from vm_trainer.management.clickgroup import cli
from vm_trainer.settings import Settings


def ensure_have_stpm():
    try:
        check_call(["swtpm", "--version"])
    except FileNotFoundError:
        print("swtpm is not installed. Installing...")
        check_call(["sudo", "apt-get", "update"])
        check_call(["sudo", "apt-get", "install", "-y", "swtpm-tools"])


@cli.command(help="Starts a fake TPM device for QEMU")
def tpm_emulator() -> None:
    ensure_have_stpm()
    settings = Settings()
    tpm_dir = settings.tpm_dir()
    socket_path = settings.tpm_socket_path()
    check_call(["swtpm", "socket", "--tpmstate", f"dir={tpm_dir}", "--ctrl", f"type=unixio,path={socket_path}", "--tpm2", "--log", "level=20"])
