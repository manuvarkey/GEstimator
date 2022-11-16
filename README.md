# GEstimator

GEstimator is a civil estimation software for preparing cost and quantity estimates of civil/electrical works along with detailed rate analysis. It supports multiple user databases and comes bundled with **DSR 2021 (Civil)** and **DSR 2022 (E&M)**.

The program is organised in three tabs - Schedule Items, Details of Measurements and Resource Items. Schedule Items implements an interface to input the estimate schedule/import the schedule from a .xlsx file. On editing (`Edit`) any schedule item an Analysis View is displayed allowing edit of the rate analysis. Details of Measurements allows the details of measurements to be recorded against items added under Schedule Items. Resource Items allows input/manipulation of the resources like material, labour and tools/plants upon which the rate analysis will be framed.

The estimates can be rendered into a .xlsx document from `Menu->Export...`. The exported sheet includes - the schedule of rates for the work, schedule of resources, details of measurements, resource usage for the work and analysis of rates for various items of work.

Homepage: https://manuvarkey.github.io/GEstimator/

## Screenshots

![Image 1](https://raw.githubusercontent.com/manuvarkey/GEstimator/master/screenshots/schedule.png)
![Image 2](https://raw.githubusercontent.com/manuvarkey/GEstimator/master/screenshots/resource.png)
![Image 3](https://raw.githubusercontent.com/manuvarkey/GEstimator/master/screenshots/analysis.png)
![Image 4](https://raw.githubusercontent.com/manuvarkey/GEstimator/master/screenshots/addlibrary.png)
![Image 5](https://raw.githubusercontent.com/manuvarkey/GEstimator/master/screenshots/measurements.png)

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

### GTK3  (v3.36)
