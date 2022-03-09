import pathlib
from setuptools import setup
from lfshelper import __version__

parent_dir = pathlib.Path(__file__).parent
readme = "Provides a python3 command line tool which can generate shell scripts to build a LFS system."

setup(
    name = 'lfshelper',
    version = __version__,
    #url = '',
    license = 'MIT',
    #author = '',
    #author_email = '',
    description = 'Tools to help building a LFS system.',
    long_description = readme,
    long_description_content_type = "text/markdown",
    packages = ['lfshelper'],
    entry_points = {
        "console_scripts": [
            "lfsbuild=lfshelper.__main__:main"
        ]
    },
    install_requires = ['lxml']
)
