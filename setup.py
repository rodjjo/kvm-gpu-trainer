import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

with open("requirements.txt", "r") as fp:
    requirements = fp.read()

setuptools.setup(
    name="vm-trainer",
    version="0.1.0",
    author="rodrigo.araujo",
    author_email="rodjjo@gmail.com",
    description="A tool to create and launch virtual machines using qemu kvm with gpu passthroug support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rodjjo/kvm-gpu-trainer",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: Arch-Linux",
    ],
    install_requires=requirements,
    python_requires='>=3.5',
    scripts=['vm-trainer']
)
