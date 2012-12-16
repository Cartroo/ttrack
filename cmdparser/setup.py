#!/usr/bin/python

from setuptools import setup
from cmdparser import __version__


setup(name="cmdparser",
      version=__version__,
      author="Andy Pearce",
      author_email="andy@andy-pearce.com",
      packages=["cmdparser"],
      url="https://github.com/Cartroo/ttrack",
      license="LICENSE.txt",
      description="Command parsing extensions to the cmd module.",
      long_description=open("README.rst").read()
)

