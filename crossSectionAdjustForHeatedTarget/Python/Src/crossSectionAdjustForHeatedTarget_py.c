/*
# <<BEGIN-copyright>>
# Copyright (c) 2016, Lawrence Livermore National Security, LLC.
# Produced at the Lawrence Livermore National Laboratory.
# Written by the LLNL Nuclear Data and Theory group
#         (email: mattoon1@llnl.gov)
# LLNL-CODE-683960.
# All rights reserved.
# 
# This file is part of the FUDGE package (For Updating Data and 
#         Generating Evaluations)
# 
# When citing FUDGE, please use the following reference:
#   C.M. Mattoon, B.R. Beck, N.R. Patel, N.C. Summers, G.W. Hedstrom, D.A. Brown, "Generalized Nuclear Data: A New Structure (with Supporting Infrastructure) for Handling Nuclear Data", Nuclear Data Sheets, Volume 113, Issue 12, December 2012, Pages 3145-3171, ISSN 0090-3752, http://dx.doi.org/10. 1016/j.nds.2012.11.008
# 
# 
#     Please also read this link - Our Notice and Modified BSD License
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the disclaimer below.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the disclaimer (as noted below) in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of LLNS/LLNL nor the names of its contributors may be used
#       to endorse or promote products derived from this software without specific
#       prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL LAWRENCE LIVERMORE NATIONAL SECURITY, LLC,
# THE U.S. DEPARTMENT OF ENERGY OR CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# 
# Additional BSD Notice
# 
# 1. This notice is required to be provided under our contract with the U.S.
# Department of Energy (DOE). This work was produced at Lawrence Livermore
# National Laboratory under Contract No. DE-AC52-07NA27344 with the DOE.
# 
# 2. Neither the United States Government nor Lawrence Livermore National Security,
# LLC nor any of their employees, makes any warranty, express or implied, or assumes
# any liability or responsibility for the accuracy, completeness, or usefulness of any
# information, apparatus, product, or process disclosed, or represents that its use
# would not infringe privately-owned rights.
# 
# 3. Also, reference herein to any specific commercial products, process, or services
# by trade name, trademark, manufacturer or otherwise does not necessarily constitute
# or imply its endorsement, recommendation, or favoring by the United States Government
# or Lawrence Livermore National Security, LLC. The views and opinions of authors expressed
# herein do not necessarily state or reflect those of the United States Government or
# Lawrence Livermore National Security, LLC, and shall not be used for advertising or
# product endorsement purposes.
# 
# <<END-copyright>>
*/

#include <Python.h>
#include <string.h>

#include <crossSectionAdjustForHeatedTarget.h>

static char constantLimit[] = "constant";
static char oneOverVLimit[] = "oneOverV";
static char thresholdLimit[] = "threshold";

static PyObject *crossSectionAdjustForHeatedTarget_py( PyObject *self, PyObject *args, PyObject *keywords );

static int addedItemToList( PyObject *list, PyObject *item );
static PyObject *buildPythonFloatList( int n, double *d );
/*
***********************  __init__  **********************
*/
static PyObject *crossSectionAdjustForHeatedTarget_py( PyObject *self, PyObject *args, PyObject *keywords ) {

    int i, n, err, n_pairs, heatAllPoints = 0, doNotThin = 0, heatAllEDomain = 1;
    size_t n_pairs_p;
    double massRatio, T, f_interpolation = 0.002, *E_cs_in, *E_cs_out, EMin;
    static char *keywordlist[] = { "massRatio", "T", "EMin", "E_cs", "lowerlimit", "upperlimit", "interpolationAccuracy", "heatAllPoints", "doNotThin",
        "heatAllEDomain", NULL };
    PyObject *p, *ll, *iterator, *E_cs, *xy;
    crossSectionAdjustForHeatedTarget_limit lowerlimit = crossSectionAdjustForHeatedTarget_limit_constant;
    crossSectionAdjustForHeatedTarget_limit upperlimit = crossSectionAdjustForHeatedTarget_limit_constant;
    char Str[128], *Str_lowerlimit = constantLimit, *Str_upperlimit = oneOverVLimit;
    crossSectionAdjustForHeatedTarget_info info;

    info.mode = 0;
    info.verbose = 0;
    info.InfoStats = 0;
    info.WarningStats = 0;
    info.ErrorStats = 0;

    if( !PyArg_ParseTupleAndKeywords( args, keywords, "dddO|ssdiii", keywordlist, &massRatio, &T, &EMin, &p, &Str_lowerlimit, &Str_upperlimit, 
        &f_interpolation, &heatAllPoints, &doNotThin, &heatAllEDomain ) ) return( NULL );

    if( heatAllPoints ) info.mode |= crossSectionAdjustForHeatedTarget_mode_all;
    if( heatAllEDomain ) info.mode |= crossSectionAdjustForHeatedTarget_mode_allEDomain;
    if( doNotThin ) info.mode |= crossSectionAdjustForHeatedTarget_mode_do_not_thin;

    if( strcmp( Str_lowerlimit, constantLimit ) == 0 ) {
        lowerlimit = crossSectionAdjustForHeatedTarget_limit_constant; }
    else if( strcmp( Str_lowerlimit, oneOverVLimit ) == 0 ) {
        lowerlimit = crossSectionAdjustForHeatedTarget_limit_one_over_v; }
    else if( strcmp( Str_lowerlimit, thresholdLimit ) == 0 ) {
        lowerlimit = crossSectionAdjustForHeatedTarget_limit_threshold; }
    else {
        PyErr_SetString( PyExc_TypeError, "invalid lowerlimit string" );
        return( NULL );
    }

    if( strcmp( Str_upperlimit, constantLimit ) == 0 ) {
        upperlimit = crossSectionAdjustForHeatedTarget_limit_constant; }
    else if( strcmp( Str_upperlimit, oneOverVLimit ) == 0 ) {
        upperlimit = crossSectionAdjustForHeatedTarget_limit_one_over_v; }
    else {
        PyErr_SetString( PyExc_TypeError, "invalid upperlimit string" );
        return( NULL );
    }

    if( massRatio <= 0. ) {
        PyErr_SetString( PyExc_TypeError, "massRatio must be greater than 0" );
        return( NULL );
    }
    if( T <= 0. ) {
        PyErr_SetString( PyExc_TypeError, "T must be greater than 0" );
        return( NULL );
    }

    if( f_interpolation > 0.1 ) f_interpolation = 0.1;
    if( f_interpolation < 1e-6 ) f_interpolation = 1e-6;

    if( ( iterator = PyObject_GetIter( p ) ) == NULL ) {
        PyErr_SetString( PyExc_TypeError, "cross-section data a sequence" );
        return( NULL );
    }
    if( ( n_pairs_p = PySequence_Size( p ) ) > INT_MAX )
        return( PyErr_Format( PyExc_TypeError, "cross-section data greater than INT_MAX (= %d) (E,xsec) pairs", INT_MAX ) );
    if( ( n_pairs = (int) n_pairs_p ) < 2 ) {
        PyErr_SetString( PyExc_TypeError, "cross-section data must contain at least 2 (E,xsec) pairs" );
        return( NULL );
    }
    if( ( E_cs_in = (double *) malloc( 2 * n_pairs * sizeof( double ) ) ) == NULL ) {
        PyErr_NoMemory( );
        return( NULL );
    }
    for( i = 0; i < n_pairs; i++ ) {
        E_cs = PyIter_Next( iterator );
        if( !PyList_Check( E_cs ) ) {
            free( E_cs_in );
            Py_DECREF( iterator );
            Py_DECREF( E_cs );
            sprintf( Str, "item at index %d not a list", i );
            PyErr_SetString( PyExc_TypeError, Str );
            return( NULL );
        }
        if( PyList_Size( E_cs ) != 2 ) {
            free( E_cs_in );
            Py_DECREF( iterator );
            Py_DECREF( E_cs );
            sprintf( Str, "length of list at index %d not 2", i );
            PyErr_SetString( PyExc_TypeError, Str );
            return( NULL );
        }

        xy = PyList_GetItem( E_cs, 0 );
        if( PyFloat_Check( xy ) ) {
            E_cs_in[2 * i] = PyFloat_AsDouble( xy ); }
        else if( PyInt_Check( xy ) ) {
            E_cs_in[2 * i] = (double) PyInt_AsLong( xy ); }
        else if( PyLong_Check( xy ) ) {
            E_cs_in[2 * i] = (double) PyLong_AsLongLong( xy ); }
        else {
            free( E_cs_in );
            Py_DECREF( iterator );
            Py_DECREF( E_cs );
            sprintf( Str, "energy value at index %d not a number", i );
            PyErr_SetString( PyExc_TypeError, Str );
            return( NULL );
        }
        E_cs_in[2 * i] = PyFloat_AsDouble( xy );

        xy = PyList_GetItem( E_cs, 1 );
        if( PyFloat_Check( xy ) ) {
            E_cs_in[2 * i + 1] = PyFloat_AsDouble( xy ); }
        else if( PyInt_Check( xy ) ) {
            E_cs_in[2 * i + 1] = (double) PyInt_AsLong( xy ); }
        else if( PyLong_Check( xy ) ) {
            E_cs_in[2 * i + 1] = (double) PyLong_AsLongLong( xy ); }
        else {
            free( E_cs_in );
            Py_DECREF( iterator );
            Py_DECREF( E_cs );
            sprintf( Str, "cross-section value at index %d not a number", i );
            PyErr_SetString( PyExc_TypeError, Str );
            return( NULL );
        }
        Py_DECREF( E_cs );
    }
    Py_DECREF( iterator );

    err = crossSectionAdjustForHeatedTarget( lowerlimit, upperlimit, &info, EMin, massRatio, T, f_interpolation, n_pairs, E_cs_in, &E_cs_out );
    free( E_cs_in );

    if( err < 0 ) {
        switch( err ) {
            case -1 :                /* crossSectionAdjustForHeatedTarget needs at least two pairs of points (this is already checked above). */
                PyErr_SetString( PyExc_RuntimeError, "cross-section data must contain at least 2 (E,xsec) pairs" );
                break;
            case -2 :                /* massRatio > 0. */
                PyErr_SetString( PyExc_RuntimeError, "massRatio must be greater than 0." );
                break;
            case -3 :                /* First energy not greater than 0. */
                PyErr_SetString( PyExc_RuntimeError, "first energy point must be greater than 0" );
                break;
            case -4 :                /* T <= 0. (this is already checked above). */
                PyErr_SetString( PyExc_RuntimeError, "T must be greater than 0" );
                break;
            case -5 :                /* Energy not in ascending order (i.e., E[i] > E[i+1]). */
                PyErr_SetString( PyExc_RuntimeError, "energy not in ascending order (i.e., E[i] > E[i+1])" );
                break;
            case -6 :                /* Memory could not be allocated. */
            case -7 :
            case -11 :
                PyErr_NoMemory( );
                break;
            default :                /* Unknown err. */
                sprintf( Str, "Unknown crossSectionAdjustForHeatedTarget; err = %d", err );
                PyErr_SetString( PyExc_RuntimeError, Str );
        }
        return( NULL );
    }
    n = 2 * err;
    ll = PyList_New( 0 );
    for( i = 0; ( ll != NULL ) && ( i < n ); i += 2 ) {
        E_cs = buildPythonFloatList( 2, &(E_cs_out[i]) );
        if( addedItemToList( ll, E_cs ) != 0 ) ll = NULL;
    }
    free( E_cs_out );
    return( (PyObject *) ll );
}
/*
*********************************************************
*/
static int addedItemToList( PyObject *list, PyObject *item ) {

    if( item == NULL ) {
        Py_DECREF( list );
        return( -1 ); }
    else {
        if( PyList_Append( list, item ) != 0 ) {
            Py_DECREF( item );
            Py_DECREF( list );
            return( -1 );
        }
        Py_DECREF( item );        /* append created a new ref */
    }
    return( 0 );
}
/*
*********************************************************
*/
static PyObject *buildPythonFloatList( int n, double *d ) {

    PyObject *l = PyList_New( 0 ), *ni;
    int i;

    if( l == NULL ) return( NULL );

    for( i = 0; i < n; i++ ) {
        ni = Py_BuildValue( "d", d[i] );
        if( addedItemToList( l, ni ) != 0 ) return( NULL );
    }
    return( l );
}
/*
*********************************************************
*/
static PyMethodDef crossSectionAdjustForHeatedTargetMethods[] = {

    { "crossSectionAdjustForHeatedTarget", (PyCFunction) crossSectionAdjustForHeatedTarget_py, METH_VARARGS | METH_KEYWORDS, 
        "crossSectionAdjustForHeatedTarget( massRatio, T, crossSection, lowerlimit = 'constant', \n\
        upperlimit = 'constant', interpolationAccuracy = 0.002, heatAllPoints = 0, doNotThin = 0, EMin = 1e-11 )\n\
    Returns the cross-section adjusted for a target with temperature T.  The unit of T must be the same\n\
    as for the energy data.  massRatio is the ratio of the target's mass to the projectile's mass. \n\
    lowerlimit and upperlimit specify how the input data is extended beyond its energy range when \n\
    performing integrations over the input energy range.  Valid strings for lowerlimit are 'constant', \n\
    'oneOverV' and 'threshold'.  Valid strings for upperlimit are 'constant' and 'oneOverV'.  The heated \n\
    data is thicken to have an interpolation accuracy of interpolationAccuracy. If interpolationAccuracy \n\
    is greater [less] than 0.1 [1e-6], it is set to .1 [1e-6].  crossSection must be a list of [ E, xsec ] \n\
    numbers. For example crossSection = [ [ 1e-10, 2 ], [ 20, 2. ] ] would represent a constant cross-section\n\
    of value 2 from energy 1e-10 to 20. If heatAllPoints is true than all points are heated otherwise, a \n\
    judicial choice of E points is made. This latter procedure, which is recommended, is typically much \n\
    faster. If doNotThin is true then points are not thinned, otherwise thinning, which is recommended, is \n\
    performed. For threshold data, energy values below threshold are generated. EMin is the minimum energy \n\
    that shall be generater. For energy in MeV, the default is appropriated, otherwise, a compariable value \n\
    in the energy unit should be entered." },

    { NULL, NULL, 0, NULL }        /* Sentinel (i.e., the end of the list) */
};
/*
*********************************************************
*/
DL_EXPORT( void ) initcrossSectionAdjustForHeatedTarget( void ) {

    Py_InitModule( "crossSectionAdjustForHeatedTarget", crossSectionAdjustForHeatedTargetMethods );
}
