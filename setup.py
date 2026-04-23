from pathlib import Path

from setuptools import find_packages
from setuptools import setup


README = Path(__file__).with_name("README.md").read_text(encoding="utf-8")


setup(
    name="nic-cli",
    version="0.1.0",
    description="A clean, readable cross-platform network interface CLI for macOS, Linux, and Windows.",
    long_description=README,
    long_description_content_type="text/markdown",
    author="kidder1",
    license="MIT",
    python_requires=">=3.9",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={"console_scripts": ["nic=nic.cli:main"]},
)
