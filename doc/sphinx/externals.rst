External Packages used in Fudge
===============================

Fudge depends on some stand-alone packages that are also maintained by the LLNL Computational Nuclear Physics group.
These 'external' packages are included with Fudge but have their own source tree and documentation::

pqu
---
Also known as physicalQuantitiesWithUncertainties, this is a Python package for managing values with units and (optional) uncertainties. For more information, see the package documentation here_.

.. _here: ../../pqu/doc/html/index.html

numericalFunctions
------------------
A package written primarily in C that handles many of the low-level data containers used by ``Fudge`` and GND. Documentation is available :download:`here <../../numericalFunctions/Doc/ptwXY.pdf>`

crossSectionAdjustForHeatedTarget
---------------------------------
A package written in C for the numerically-intensive task of Doppler broadening cross sections. Documentation is available :download:`here <../../crossSectionAdjustForHeatedTarget/Doc/crossSectionAdjustForHeatedTarget.pdf>`
