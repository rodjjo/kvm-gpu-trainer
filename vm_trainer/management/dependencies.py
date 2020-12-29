from vm_trainer.components.dependencies import DependencyManager
from vm_trainer.components.tools import PackageTool
from vm_trainer.management.clickgroup import cli


@cli.command(help="Check all depedencies")
def depman_check():
    DependencyManager.check_all()


@cli.command(help="Install qemu kvm tools")
def depman_install_qemu():
    PackageTool().install_qemu_kvm()


@cli.command(help="Install git")
def depman_install_git():
    PackageTool().install_git()


@cli.command(help="Install build essentials")
def depman_install_build_tools():
    PackageTool().install_build_essential()


@cli.command(help="Install scream")
def depman_install_scream():
    PackageTool().install_scream()
