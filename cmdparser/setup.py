#!/usr/bin/python

from setuptools import setup
from cmdparser import __version__


remove_directives = ("highlight",)

def filter_directives(in_iter):
    for line in in_iter:
        if line.startswith("..") and "::" in line:
            if line.split("::", 1)[0][2:].strip() in remove_directives:
                continue
        yield line


setup(name="cmdparser",
      version=__version__,
      author="Andy Pearce",
      author_email="andy@andy-pearce.com",
      packages=["cmdparser"],
      url="http://cartroo.github.com/ttrack/cmdparser.html",
      license="LICENSE.txt",
      description="Command parsing extensions to the cmd module.",
      long_description="".join(filter_directives(open("README.rst"))),
      classifiers=[
          "Development Status :: 5 - Production/Stable",
          "Intended Audience :: Developers",
          "License :: OSI Approved :: MIT License",
          "Natural Language :: English",
          "Operating System :: OS Independent",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2",
          "Topic :: Software Development :: Libraries",
          "Topic :: Software Development :: Libraries :: Python Modules",
          "Topic :: Text Processing",
          "Topic :: Text Processing :: General"
      ]
)

