from .clickgroup import cli
from vm_trainer.components.dependencies import DependencyManager


@cli.command(help="Check all depedencies")
def dependency_check():
    DependencyManager.check_all()
