"""
Smart Knob PC Client — Setup

Install with: pip install -e .
Run with: knob-client
"""
from setuptools import setup, find_packages

setup(
    name="knob-client",
    version="1.0.0",
    description="Smart Knob Controller — PC Client",
    author="KnobControl",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "knob-client=knob_client.main:main",
        ],
    },
    python_requires=">=3.8",
    install_requires=[],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
    ],
)
