"""
Build atropos.

Cython is run when
* no pre-generated C sources are found,
* or the pre-generated C sources are out of date,
* or when --cython is given on the command line.
"""
import sys

from setuptools import setup, find_packages

# Define install and test requirements based on python version
version_info = sys.version_info
if sys.version_info < (3, 6):
    sys.stdout.write("At least Python 3.6 is required.\n")
    sys.exit(1)


with open('README.md') as f:
    README = f.read()


with open('LICENSE') as f:
    LICENSE = f.read()


setup(
    name='atropos',
    version='0.1.0',
    author='John Didion',
    author_email='github@didion.net',
    url='https://github.com/jdidion/htsget-server',
    description='Reference implementation of an htsget server.',
    long_description=README,
    license=LICENSE,
    packages=find_packages(),
    install_requires=[
        'ngsindex'
    ],
    tests_requires=['pytest'],
    entry_points={
        'console_scripts': [
            'htsget-server=htsgetserver.__main__:main'
        ]
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "License :: OSI Approved :: MIT License",
        "License :: Public Domain",
        "Natural Language :: English",
        "Programming Language :: Cython",
        "Programming Language :: Python :: 3.6"
    ]
)
