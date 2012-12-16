#!/usr/bin/python

from setuptools import setup

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
from tracklib import __version__


setup(name="ttrack",
      version=__version__,
      author="Andy Pearce",
      author_email="andy@andy-pearce.com",
      package_dir={"": "lib"},
      py_modules=["tracklib"],
      scripts=["bin/ttrack"],
      url="https://github.com/Cartroo/ttrack",
      license="LICENSE.txt",
      description="Command-line time tracking utility",
      long_description=open("README.rst").read(),
      install_requires=["cmdparser"]
)

