from setuptools import setup, find_packages 

setup(
    # Application name:
    name="GEstimator",

    # Version number (initial):
    version="2.0",

    # Application author details:
    author="Manu Varkey",
    author_email="manuvarkey@gmail.com",

    # Packages
    packages = ['estimator', 'estimator.data', 'estimator.view'],
    include_package_data = True, # Include additional files into the package
    
    data_files=[('usr/share/applications', ['gui/GEstimator.desktop']),
                ('usr/share/pixmaps', ['gui/GEstimator.svg']),
                ('bin', ['bin/GEstimator.py'])],

    # Details
    maintainer="Manu Varkey",
    maintainer_email="manuvarkey@gmail.com",
    url="https://github.com/manuvarkey/GEstimator",
    license="GPL-3.0",
    description="GEstimator is a simple civil estimation software written in Python and GTK+",

    long_description= 'GEstimator is a simple civil estimation software written in Python and GTK+. GEstimator can prepare estimates along with rate analysis and supports multiple databases.',
    
    install_requires=["appdirs", "openpyxl", "peewee", "pycairo", "PyGObject"],
    
    classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
          'Operating System :: Microsoft :: Windows',
          'Operating System :: POSIX',
          'Programming Language :: Python',
          'Topic :: Office/Business',
          ],
)
