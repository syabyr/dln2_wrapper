#!/usr/bin/env python3
"""Setup for dln2 unified wrapper package."""

from setuptools import setup, find_packages

setup(
    name="dln2",
    version="0.2.0",
    description="Unified DLN2 USB I/O Board wrapper — SPI, GPIO, I2C, ADC",
    author="syabyr",
    packages=find_packages(),
    install_requires=[
        "pyusb>=1.2",
    ],
    python_requires=">=3.9",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
    ],
)
