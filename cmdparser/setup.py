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
      long_description=open("README.rst").read(),
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: MIT License",
          "Natural Language :: English",
          "Operating System :: OS Independent"
          "Programming Language :: Python",
          "Programming Language :: Python :: 2",
          "Topic :: Software Development :: Libraries",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Topic :: Text Processing",
          "Topic :: Text Processing :: General"
      ]
)

