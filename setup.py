from setuptools import find_packages, setup

long_description = open("README.md").read()

setup(
    name="deebotozmo",
    version="0.0.0",
    url="https://github.com/And3rsL/Deebotozmo",
    description="a library for controlling certain deebot vacuums",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Andrea Liosi",
    author_email="andrea.liosi@gmail.com",
    license="GPL-3.0",
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        "Development Status :: 4 - Beta",
        # Indicate who your project is intended for
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Home Automation",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3.9",
    ],
    keywords="home automation vacuum robot",
    packages=find_packages(exclude=["contrib", "docs", "tests"]),
    package_data={"deebotozmo": ["py.typed"]},
    install_requires=list(val.strip() for val in open("requirements.txt")),
    extras_require={"cli": list(val.strip() for val in open("requirements-cli.txt"))},
    entry_points={
        "console_scripts": [
            "deebotozmo=deebotozmo.cli:cli",
        ],
    },
)
