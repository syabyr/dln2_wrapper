#!/usr/bin/env python3
"""Setup for dln2 unified wrapper package."""

from setuptools import setup, find_packages

setup(
    name="dln2",
    version="0.1.0",
    description="Unified DLN2 driver — SPI, GPIO, I2C, ADC over a single USB connection. "
                "Originally developed for the Pico USB I/O Board.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/syabyr/dln2_wrapper",
    author="IPM Group",
    author_email="contact@ipmgroup.dev",
    license="MIT",
    packages=find_packages(exclude=["examples"]),
    package_data={"dln2": ["py.typed"]},
    install_requires=[
        "pyusb>=1.2",
    ],
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: System :: Hardware",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
