
TomoTools package
===========

The tomotools package provides code for the aligment and reconstruction
of electron tomography data from TEM/STEM instruments. 

The package mostly wraps existing libraries to perform many of the lower level
operations.  Hyperspy is employed for data input/output, the astra-toolbox performs
the 3D reconstructions, and rigid transformation for alignments are calculated
and applied using the OpenCV library.


Installation
------------

Installation from GitHub:

```bash
pip install git+https://github.com/andrewherzing/tomotools.git
```
The OpenCV library is also required.  This can be installed through anaconda using:

```bash
conda install opencv
```

or through pip using:

```bash
pip install opencv-python
```

The package can be removed with:

```bash
pip uninstall tomotools
```


Usage
-----
In python or ipython:

```python
import tomotools
stack = tomotools.load('TiltSeries.mrc')
```

Documentation is very limited at this point


Documentation
-------------
Release: https://github.com/andrewherzing/tomotools

Further documentation, notebooks and examples will be made available over time.


Related projects
----------------
http://hyperspy.org/

https://opencv.org/

https://www.astra-toolbox.com/
