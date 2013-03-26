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
      url="http://cartroo.github.com/ttrack/",
      license="LICENSE.txt",
      description="Command-line time tracking utility",
      long_description=open("README.rst").read(),
      install_requires=["cmdparser"],
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Environment :: Console",
          "Intended Audience :: End Users/Desktop",
          "License :: OSI Approved :: MIT License",
          "Natural Language :: English",
          "Operating System :: OS Independent",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2",
          "Topic :: Office/Business",
          "Topic :: Office/Business :: News/Diary",
          "Topic :: Utilities"
      ]
)

