# __init__.py to make test directory a discoverable package.
# To run tests, from parent directory run:
#   python -m unittest discover
# (requires Python 2.7)

import os
import sys

# Determine package lib dir
test_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(test_dir, os.pardir))
lib_dir = os.path.join(root_dir, "lib")

# If lib dir isn't already on path, add it
if lib_dir not in (os.path.abspath(i) for i in sys.path):
    sys.path.insert(0, lib_dir)

