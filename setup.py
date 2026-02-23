# ~/catkin_ws/src/coral_inspection/setup.py
from distutils.core import setup
from catkin_pkg.python_setup import generate_distutils_setup

d = generate_distutils_setup(
    packages=['coral_inspection', 'coral_inspection.tools'],
    package_dir={'': 'src'}
)

setup(**d)
