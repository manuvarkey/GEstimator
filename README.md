# GEstimator

GEstimator is a civil estimation software for preparing cost estimates of civil/electrical works along with detailed rate analysis. It supports multiple user databases and comes bundled with **DSR 2016 (Civil)** and **DSR 2016 (E&M)**.

The program is organised in two tabs - Schedule Items and Resource Items. Schedule Items implements an interface to input the estimate schedule/import the schedule from a .xlsx file. On editing (`Edit`) any schedule item an Analysis View is displayed allowing edit of the rate analysis. Resource Items allows input/manipulation of the resources like material, labour and tools/plants upon which the rate analysis will be framed.

The estimates can be rendered into a .xlsx document from `Menu->Export...`. The exported sheet includes - the schedule of rates for the work, schedule of resources, resource usage for the work and analysis of rates for various items of work.

Homepage: https://manuvarkey.github.io/GEstimator/

## Installation

Latest source code and binaries for GEstimator can be downloaded from this page under `Releases`.

### Source installation

Application can be installed using `python setup.py install`. It has been tested with Python 3.4 and Gtk 3.18, and has the following extra dependencies.

## Dependencies:

### Python 3 (v3.5)

Python Modules:

* undo - Included along with distribution.
* openpyxl (v2.5.1) - Not included
* appdirs (v1.4.3) - Not included
* jdcal - Not included
* et_xmlfile - Not included
* peewee (v3.2.0) - Not included
* pyblake2 - Not included
* pycairo - Not included
* PyGObject - Not included

### GTK3  (v3.30)
[![Run on Repl.it](https://repl.it/badge/github/manuvarkey/GEstimator)](https://repl.it/github/manuvarkey/GEstimator)