import os
from pathlib import Path

BASE_DIR = Path(os.path.dirname(__file__)).absolute()
VMS_DIR = Path(BASE_DIR).parent.joinpath('vms')
