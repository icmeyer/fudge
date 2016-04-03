Basic translating between ENDF and GND
======================================

In this first tutorial, we will write two codes: 
    
    * ``endf2gnd.py`` : a code to translate ENDF formatted data into the GND format
    * ``gnd2endf.py`` : a code to translate GND formatted data into ENDF

In both scripts (and all the others we will write), we will use the Python `argparse` module to 
manage the command line options of the scripts.  Before we get to that, lets just start by learning how to translate between ENDF and GND.

Translating from ENDF into GND
------------------------------
Let's experiment with fudge in the Python shell.

::

    $ python
    Python 2.7.1 (r271:86832, Jun 16 2011, 16:59:05) 
    [GCC 4.2.1 (Based on Apple Inc. build 5658) (LLVM build 2335.15.00)] on darwin
    Type "help", "copyright", "credits" or "license" for more information.

    
First, import the ``endfFileToGND`` function from ``fudge.legacy.converting``:

    >>> from fudge.legacy.converting.endfFileToGND import endfFileToGND
    
I assume that you have an ENDF formatted file somewhere and for the sake of argument, I'll 
assume that it is ``n-001_H_001.endf`` and that it is in the current directory, ``'.'``.  Given this, 
simply do:

    >>> myEval, myCov = endfFileToGND( 'n-001_H_001.endf', toStdOut=True, skipBadData=True )
    
Before hitting return, note a few things.  First, the ``endfFileToGND()`` function takes one mandatory argument, the ENDF file name, and returns two values.  The first is an reference to a ``reactionSuite`` instance containing the entire `GND` file.  That's right, this function reads and translates the data at the same time.  The second value is an reference to a ``covarianceSuite`` instance.  If the original ENDF file has no covariances, then the second value will be set to ``None``.

The other arguments ``toStdOut`` and ``skipBadData`` do not need to be specified.  The ``skipBadData`` option tells ``fudge`` to keep going when reading an ENDF file, even if it is "broken".  ``Fudge`` is picky and will otherwise throw an exception when it encounters bad or malformed data (an all to common occurrance sadly).  The ``toStdOut`` option tells ``fudge`` to redirect all warnings and errors to ``stdout`` rather than ``stderr``.

So, let's hit return and see what happens:

    >>> myEval, myCov = endfFileToGND( 'n-001_H_001.endf', toStdOut=True, skipBadData=True )
      2 [3, 4, 33] : MF=4, LTT = 1
    102 [3, 6, 33] : MF=6 : ZAP=0, LAW=2, LANG=0 : ZAP=1002, LAW=4
      1 [3, 33]

Voila, your ENDF file is translated into GND.  The first number listed is the ENDF reaction designator MT (2, 102 and 1 are present in this file).  The list following the MT is the list of observables for which there is data in this reaction, i.e. the list of MF's.  The final set of values denote any special formats for those MF's.

To write translated results to a file, we need to use the ``toXMLList()`` member functions of ``myEval`` and ``myCov``:
    
    >>> open( "n-001_H_001.gnd.xml", mode='w' ).writelines( myEval.toXMLList( {'verbosity':0} ) )
    >>> if myCov is not None:
    >>>     open( "n-001_H_001.gndCov.xml", mode='w' ).writelines( myCov.toXMLList( {'verbosity':0} ) )

In both cases, we must hand the ``toXMLList()`` member function a dictionary containing any extra processing directives (in this case, we simply set 'verbosity' to 0 to indicate that we want the output to be quiet).

Translating GND files back into ENDF
------------------------------------

Now let us reconstruct the original ENDF file.  All ``reactionSuite`` instances contain a member function ``toENDF6()``.  Let's try it out:

    >>> myENDF = myEval.toENDF6( {'verbosity':0}, covarianceSuite=myCov )
    >>> open( "junk.endf", mode='w' ).write( myENDF )
    
Now you should quit Python (using ^d), and check out what you made.

::

    $ diff junk.endf n-001_H_001.endf 
    1c1
    <                                                                      1 0  0
    ---
    >  $Rev:: 532      $  $Date:: 2011-12-05#$                             1 0  0    0
    93c93
    <                                 1        451        101          0 125 1451   92
    ---
    >                                 1        451        101          5 125 1451   92
    95,102c95,102
    <                                 3          1         35          0 125 1451   94
    <                                 3          2         35          0 125 1451   95
    <                                 3        102         35          0 125 1451   96
    <                                 4          2        196          0 125 1451   97
    <                                 6        102        201          0 125 1451   98
    <                                33          1          5          0 125 1451   99
    <                                33          2         21          0 125 1451  100
    <                                33        102         21          0 125 1451  101
    ---
    >                                 3          1         35          4 125 1451   94
    >                                 3          2         35          4 125 1451   95
    >                                 3        102         35          5 125 1451   96
    >                                 4          2        196          4 125 1451   97
    >                                 6        102        201          4 125 1451   98
    >                                33          1          5          5 125 1451   99
    >                                33          2         21          5 125 1451  100
    >                                33        102         21          5 125 1451  101
    113c113
    <          30          5         96          2          0          0 125 3  1    3
    ---
    >          30          5         96          2                       125 3  1    3
    149c149
    <          96          2          0          0          0          0 125 3  2    3
    ---
    >          96          2                                             125 3  2    3
    185c185
    <          30          5         96          2          0          0 125 3102    3
    ---
    >          30          5         96          2                       125 3102    3
    223c223
    <          96          2          0          0          0          0 125 4  2    4
    ---
    >          96          2                                             125 4  2    4
    420c420
    <           2          2          0          0          0          0 125 6102    3
    ---
    >           2          2                                             125 6102    3
    423c423
    <          96          2          0          0          0          0 125 6102    6
    ---
    >          96          2                                             125 6102    6
    617c617
    <           2          2          0          0          0          0 125 6102  200
    ---
    >           2          2                                             125 6102  200    

Not bad...  There are obviously several differences.  Let's examine them:

**Line 1:**
      The ``$Rev::$`` and ``$Date::`` fields are put in by the NNDC on the 
      very first line of every ENDF file simply to enable subversion version control
      keyword substitutions.  This line is not part of the ENDF standard and may be 
      safely ignored.
**Lines 92-101:**
      These lines are the ENDF dictionary in the end of the free text discriptive
      section (MF1/MT451).  The only difference here is that the ENDF section version numbers 
      were are set to 0.  In this case, this messes up the versioning of ``n-001_H_001.endf``, 
      however we note that few evaluators remember to set these values in practice.
**Remainder of lines:**
      In each case, the original ENDF file did not quite follow the ENDF format
      strictly and entered empty strings where the integer ``0`` should have been used.

When translating from ENDF, you may notice some substantial differences between the original and re-translated file.
Some differences are due to sections that are not yet translated to the new format (for example, delayed gammas from ENDF
MF 1 MT 460 are not yet translated). Other differences include:

    - masses, which appear many times in ENDF and are often inconsistent. In a GND file, the mass is stored only once,
      so upon translation back to ENDF inconsistent masses are overwritten.

    - interpolation regions: ENDF files permit using different interpolation (lin-lin, log-lin, etc) in different
      regions. GND also supports this, but where possible we have merged two or more regions into a single region (for
      example, 'flat' interpolation regions can be merged with lin-lin regions with no loss of precision). Also, ENDF
      files may contain discontinuous functions within a single interpolation region. Upon translating to GND, these are
      converted into multiple regions.

    - Improperly-formatted ENDF files: the GND translation tool strictly interprets the ENDF format as defined in the
      June 2010 version of the ENDF manual (available at https://ndclx4.bnl.gov/gf/project/endf6man). Some differences come
      from files in the ENDF library that do not strictly follow the format. As a common example, some ENDF files contain
      non-zero data in a reserved field. After translation, the entry is reset to '0'.



Reading GND XML files
---------------------

If I didn't have pre-made instances of ``reactionSuite`` and ``covarianceSuite``, how would I read in the XML files?  For this purpose, both the ``fudge.gnd.reactionSuite`` and ``fudge.gnd.covariances`` have the factory function ``readXML()``.  To use them do:

    >>> from fudge.gnd import reactionSuite, covariances
    >>> myOtherEval = reactionSuite.readXML( "n-001_H_001.gnd.xml" )

This reads in the evaluation itself.  To read in the covariance, we need to tell the `covariances.readXML()` function where the evaluation is so that it can set up the hyperlinks correctly:

    >>> myOtherCov = covariances.readXML( "n-001_H_001.gndCov.xml", reactionSuite=myOtherEval )

Setting up the translator scripts
---------------------------------

In this final section of the first tutorial, we'll actually make the two scripts ``endf2gnd.py`` and ``gnd2endf.py``.  Let's start by making the files and then editing the first:
::

    $ touch endf2gnd.py gnd2endf.py
    $ chmod u+x endf2gnd.py gnd2endf.py
    $ vim endf2gnd.py 
    
For ``endf2gnd.py``, we want to read one ENDF file and write the GND evaluation file and (if present) the GND covariance file. Since there are two output files, we want them to have the same prefix for bookkeeping purposes.  So, here is my version of ``endf2gnd.py`` (download it :download:`here <endf2gnd.py>`):
::

    #! /usr/bin/env python
    import argparse
    from fudge.legacy.converting.endfFileToGND import endfFileToGND
    
    # Process command line options
    parser = argparse.ArgumentParser(description='Translate ENDF into GND')
    parser.add_argument('inFile', type=str, help='The ENDF file you want to translate.' )
    parser.add_argument('-o', dest='outFilePrefix', default=None, help='''Specify the output file's prefix to be ``outFilePrefix``.  The outputted files have extensions ".gnd.xml" and ".gndCov.xml"vfor the GND main evaluations and covariance files and ".endf" for ENDF files.''' )
    args = parser.parse_args()
    
    # Compute output file names
    if args.outFilePrefix != None:
        outEvalFile = args.outFilePrefix + '.gnd.xml'
        outCovFile = args.outFilePrefix + '.gndCov.xml'
    else:
        outEvalFile = args.inFile.replace( '.endf', '.gnd.xml' )
        outCovFile = args.inFile.replace( '.endf', '.gndCov.xml' )
        
    # Now translate
    myEval, myCov = endfFileToGND( args.inFile, toStdOut=True, skipBadData=True )
    open( outEvalFile, mode='w' ).writelines( line+'\n' for line in myEval.toXMLList( {'verbosity':0} ) )
    if myCov is not None:
         open( outCovFile, mode='w' ).writelines( line+'\n' for line in myCov.toXMLList( {'verbosity':0} ) )

I urge you to try it out.  If you are unsure how to use it, type ``./endf2gnd.py --help``.

``gnd2endf.py`` is similar.  However, we need to specify an input file prefix and the optionally the  output file name.  This is my version of ``gnd2endf.py`` (download it :download:`here <gnd2endf.py>`):
::

    #! /usr/bin/env python
    import argparse, os
    from fudge.gnd import reactionSuite, covariances
    
    # Process command line options
    parser = argparse.ArgumentParser(description='Translate GND into ENDF')
    parser.add_argument('inFilePrefix', type=str, help='The prefix of the GND files you want to translate.' )
    parser.add_argument('-o', dest='outFile', default=None, help='Specify the output file' )
    args = parser.parse_args()
    
    # Compute input file names
    inEvalFile = args.inFilePrefix + '.gnd.xml'
    inCovFile = args.inFilePrefix + '.gndCov.xml'
    
    # Compute the output file name
    if args.outFile == None: outFile = args.inFilePrefix + '.endf'
    else:                    outFile = args.outFile
        
    # Read in XML files
    myEval = reactionSuite.readXML( inEvalFile )
    if os.path.exists( inCovFile ): myCov = covariances.readXML( inCovFile, reactionSuite=myEval )
    else:                           myCov = None
    
    # Now translate
    open( outFile, mode='w' ).write( myEval.toENDF6( {'verbosity':0}, covarianceSuite=myCov ) )

