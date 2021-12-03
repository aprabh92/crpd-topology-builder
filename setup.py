import setuptools
import sys

with open("README.md", "r") as fh:
    long_description = fh.read()

req_line = [req.strip() for req in open("requirements.txt").readlines()]
install_req = list(filter(None, req_line))

setuptools.setup(
    name="topo-builder-ARD92",
    version="0.1",
    author="Aravind",
    description="cRPD topology builder",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ARD92/crpd-topology-builder",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=2.7',
    install_requires=install_req
)
