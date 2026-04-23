import re
from pathlib import Path

from setuptools import find_packages
from setuptools import setup


README = Path(__file__).with_name("README.md").read_text(encoding="utf-8")
VERSION = re.search(
    r'^__version__\s*=\s*"([^"]+)"',
    Path(__file__).with_name("src").joinpath("nic", "__init__.py").read_text(encoding="utf-8"),
    re.MULTILINE,
).group(1)


setup(
    name="nic-cli",
    version=VERSION,
    description="A clean, readable cross-platform network interface CLI for macOS, Linux, and Windows.",
    long_description=README,
    long_description_content_type="text/markdown",
    author="kidder1",
    author_email="89340217+Kidder1@users.noreply.github.com",
    url="https://github.com/Kidder1/nic",
    python_requires=">=3.9",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    entry_points={"console_scripts": ["nic=nic.cli:main"]},
)
