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

#include <math.h>
#include <float.h>

#include "ptwXY.h"
#include <nf_Legendre.h>
#include <nf_integration.h>

typedef struct ptwXY_integrateWithFunctionInfo_s {
    int degree;
    ptwXY_createFromFunction_callback func;
    void *argList;
    ptwXY_interpolation interpolation;
    double x1, x2, y1, y2;
} ptwXY_integrateWithFunctionInfo;

static nfu_status ptwXY_integrateWithFunction2( nf_Legendre_GaussianQuadrature_callback integrandFunction, void *argList, double x1,
        double x2, double *integral );
static nfu_status ptwXY_integrateWithFunction3( double x, double *y, void *argList );
/*
************************************************************
*/
nfu_status ptwXY_f_integrate( statusMessageReporting *smr, ptwXY_interpolation interpolation, double x1, double y1, 
        double x2, double y2, double *value ) {

    nfu_status status = nfu_Okay;
    double r;

    *value = 0.;
    switch( interpolation ) {
    case ptwXY_interpolationLinLin :                            /* x linear, y linear */
        *value = 0.5 * ( y1 + y2 ) * ( x2 - x1 );
        break;
    case ptwXY_interpolationLogLin :                            /* x linear, y log */
        if( ( y1 <= 0. ) || ( y2 <= 0. ) ) {
            smr_setReportError2( smr, nfu_SMR_libraryID, nfu_badIntegrationInput, 
                    "0 or negative values for log-y integration: y1 = %.17e, y2 = %.17e", y1, y2 );
            status = nfu_badIntegrationInput; }
        else {
            r = y2 / y1;
            if( fabs( r - 1. ) < 1e-4 ) {
                r = r - 1.;
                *value = y1 * ( x2 - x1 ) / ( 1. + r * ( -0.5 + r * ( 1. / 3. + r * ( -0.25 + .2 * r ) ) ) ); }
            else {
                *value = ( y2 - y1 ) * ( x2 - x1 ) / log( r );
            }
        }
        break;
    case ptwXY_interpolationLinLog :                            /* x log, y linear */
        if( ( x1 <= 0. ) || ( x2 <= 0. ) ) {
            smr_setReportError2( smr, nfu_SMR_libraryID, nfu_badIntegrationInput, 
                    "0 or negative values for log-x integration: x1 = %.17e, x2 = %.17e", x1, x2 );
            status = nfu_badIntegrationInput; }
        else {
            r = x2 / x1;
            if( fabs( r - 1. ) < 1e-4 ) {
                r = r - 1.;
                r = r * ( -0.5 + r * ( 1. / 3. + r * ( -0.25 + .2 * r ) ) );
                *value = x1 * ( y2 - y1 ) * r / ( 1. + r ) + y2 * ( x2 - x1 ); }
            else {
                *value = ( y1 - y2 ) * ( x2 - x1 ) / log( r ) + x2 * y2 - x1 * y1;
            }
        }
        break;
    case ptwXY_interpolationLogLog :                            /* x log, y log */
        if( ( x1 <= 0. ) || ( x2 <= 0. ) || ( y1 <= 0. ) || ( y2 <= 0. ) ) {
            smr_setReportError2( smr, nfu_SMR_libraryID, nfu_badIntegrationInput, 
                    "0 or negative values for log-x and log-y integration: x1 = %.17e, y1 = %.17e, x2 = %.17e, y2 = %.17e", 
                    x1, y1, x2, y2 );
            status = nfu_badIntegrationInput; }
        else {
            int i, n;
            double a, z, lx, ly, s, f;

            r = y2 / y1;
            if( fabs( r - 1. ) < 1e-4 ) {
                ly = ( y2 - y1 ) / y1;
                ly = ly * ( 1. + ly * ( -0.5 + ly * ( 1. / 3. - 0.25 * ly ) ) ); }
            else {
                ly = log( r );
            }
            r = x2 / x1;
            if( fabs( r - 1. ) < 1e-4 ) {
                lx = ( x2 - x1 ) / x1;
                lx = lx * ( 1 + lx * ( -0.5 + lx * ( 1. / 3. - 0.25 * lx ) ) ); }
            else {
                lx = log( r );
            }
            a = ly / lx;
            if( fabs( r - 1. ) < 1e-3 ) {
                z = ( x2 - x1 ) / x1;
                n = (int) a;
                if( n > 10 ) n = 12;
                if( n < 4 ) n = 6;
                a = a - n + 1;
                f = n + 1.;
                for( i = 0, s = 0.; i < n; i++, a++, f-- ) s = ( 1. + s ) * a * z / f;
                *value = y1 * ( x2 - x1 ) * ( 1. + s ); }
            else {
                *value = y1 * x1 * ( pow( r, a + 1. ) - 1. ) / ( a + 1. );
            }
        }
        break;
    case ptwXY_interpolationFlat :                            /* x ?, y flat */
        *value = y1 * ( x2 - x1 );
        break;
    case ptwXY_interpolationOther :
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_otherInterpolation, "Other interpolation not supported for integration." );
        status = nfu_otherInterpolation;
    }
    return( status );
}
/*
************************************************************
*/
nfu_status ptwXY_integrate( statusMessageReporting *smr, ptwXYPoints *ptwXY, double domainMin, double domainMax, double *value ) {

    int64_t i, n = ptwXY->length;
    double dSum, x, y, x1, x2, y1, y2, _sign = 1.;
    ptwXYPoint *point;
    nfu_status status;

    *value = 0.;

    if( ptwXY->status != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
        return( nfu_badSelf );
    }
    if( ptwXY->interpolation == ptwXY_interpolationOther ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_otherInterpolation, "Other interpolation not supported for integration." );
        return( nfu_otherInterpolation );
    }

    if( n < 2 ) return( nfu_Okay );

    if( domainMax < domainMin ) {
        x = domainMin;
        domainMin = domainMax;
        domainMax = x;
        _sign = -1.;
    }

    if( ( status = ptwXY_simpleCoalescePoints( smr, ptwXY ) ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
        return( status );
    }

    for( i = 0, point = ptwXY->points; i < n; i++, point++ ) {
        if( point->x >= domainMin ) break;
    }
    if( i == n ) return( nfu_Okay );

    x2 = point->x;
    y2 = point->y;
    if( i > 0 ) {
        if( x2 > domainMin ) {
            x1 = point[-1].x;
            y1 = point[-1].y;
            if( ( status = ptwXY_interpolatePoint( smr, ptwXY->interpolation, domainMin, &y, x1, y1, x2, y2 ) ) != nfu_Okay ) {
                smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
                return( status );
            }
            if( x2 > domainMax ) {
                double rangeMax;

                if( ( status = ptwXY_interpolatePoint( smr, ptwXY->interpolation, domainMax, &rangeMax, x1, y1, x2, y2 ) ) == nfu_Okay ) {
                    status = ptwXY_f_integrate( smr, ptwXY->interpolation, domainMin, y, domainMax, rangeMax, value );
                }
                if( status != nfu_Okay ) smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
                return( status ); }
            else {
                if( ( status = ptwXY_f_integrate( smr, ptwXY->interpolation, domainMin, y, x2, y2, value ) ) != nfu_Okay ) {
                    smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
                    return( status );
                }
            }
        }
    }
    i++;
    point++;
    for( ; i < n; i++, point++ ) {
        x1 = x2;
        y1 = y2;
        x2 = point->x;
        y2 = point->y;
        if( x2 > domainMax ) {
            if( ( status = ptwXY_interpolatePoint( smr, ptwXY->interpolation, domainMax, &y, x1, y1, x2, y2 ) ) != nfu_Okay ) {
                smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
                return( status );
            }
            if( ( status = ptwXY_f_integrate( smr, ptwXY->interpolation, x1, y1, domainMax, y, &dSum ) ) != nfu_Okay ) {
                smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
                return( status );
            }
            *value += dSum;
            break;
        }
        if( ( status = ptwXY_f_integrate( smr, ptwXY->interpolation, x1, y1, x2, y2, &dSum ) ) != nfu_Okay ) {
            smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
            return( status );
        }
        *value += dSum;
    }

    *value *= _sign;

    return( nfu_Okay );
}
/*
************************************************************
*/
nfu_status ptwXY_integrateDomain( statusMessageReporting *smr, ptwXYPoints *ptwXY, double *value ) {

    nfu_status status = nfu_Okay;

    *value = 0;

    if( ptwXY->status != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
        return( nfu_badSelf );
    }

    if( ptwXY->length > 0 ) {
        double domainMin, domainMax;

        if( ptwXY_domainMin( smr, ptwXY, &domainMin ) != nfu_Okay ) smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
        if( ptwXY_domainMax( smr, ptwXY, &domainMax ) != nfu_Okay ) smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
        if( ( status = ptwXY_integrate( smr, ptwXY, domainMin, domainMax, value ) ) != nfu_Okay )
            smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
    }
    return( status );
}
/*
************************************************************
*/
nfu_status ptwXY_normalize( statusMessageReporting *smr, ptwXYPoints *ptwXY ) {
/*
*   This function assumes ptwXY_integrateDomain coalesces the points.
*/
    int64_t i1;
    nfu_status status = nfu_Okay;
    double sum;

    if( status != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
        return( nfu_badSelf );
    }

    if( ( status = ptwXY_integrateDomain( smr, ptwXY, &sum ) ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
        return( status );
    }

    if( sum == 0. ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badNorm, "Cannot normalize curve with 0 norm." );
        status = nfu_badNorm; }
    else {
        for( i1 = 0; i1 < ptwXY->length; i1++ ) ptwXY->points[i1].y /= sum;
    }
    return( status );
}
/*
************************************************************
*/
nfu_status ptwXY_integrateDomainWithWeight_x( statusMessageReporting *smr, ptwXYPoints *ptwXY, double *value ) {

    nfu_status status = nfu_Okay;
    double domainMin, domainMax;

    *value = 0.;

    if( ptwXY->status != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
        return( nfu_badSelf );
    }

    if( ptwXY->length < 2 ) return( nfu_Okay );

    if( ptwXY_domainMin( smr, ptwXY, &domainMin ) != nfu_Okay ) smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
    if( ptwXY_domainMax( smr, ptwXY, &domainMax ) != nfu_Okay ) smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
    if( ( status = ptwXY_integrateWithWeight_x( smr, ptwXY, domainMin, domainMax, value ) ) != nfu_Okay )
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
    return( status );
}
/*
************************************************************
*/
nfu_status ptwXY_integrateWithWeight_x( statusMessageReporting *smr, ptwXYPoints *ptwXY, double domainMin, double domainMax, 
        double *value ) {

    int64_t i, n = ptwXY->length;
    double sum = 0., x, y, x1, x2, y1, y2, _sign = 1., a1, inv_a1, a1x1, a1x2;
    ptwXYPoint *point;
    nfu_status status;

    *value = 0.;

    if( ptwXY->status != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
        return( nfu_badSelf );
    }

    if(     ( ptwXY->interpolation != ptwXY_interpolationLinLin ) && 
            ( ptwXY->interpolation != ptwXY_interpolationLogLin ) &&
            ( ptwXY->interpolation != ptwXY_interpolationFlat ) ) {
        smr_setReportError2( smr, nfu_SMR_libraryID, nfu_unsupportedInterpolation,
            "Unsupported interpolation = '%s'", ptwXY->interpolationString );
        return( nfu_unsupportedInterpolation );
    }

    if( n < 2 ) return( nfu_Okay );

    if( domainMax < domainMin ) {
        x = domainMin;
        domainMin = domainMax;
        domainMax = x;
        _sign = -1.;
    }

    if( ptwXY_simpleCoalescePoints( smr, ptwXY ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
        return( nfu_Error );
    }

    for( i = 0, point = ptwXY->points; i < n; ++i, ++point ) {
        if( point->x >= domainMin ) break;
    }
    if( i == n ) return( nfu_Okay );

    x2 = point->x;
    y2 = point->y;
    if( i > 0 ) {
        if( x2 > domainMin ) {
            if( ( status = ptwXY_interpolatePoint( smr, ptwXY->interpolation, domainMin, &y, point[-1].x, point[-1].y, x2, y2 ) ) != nfu_Okay ) {
                smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
                return( status );
            }
            x2 = domainMin;
            y2 = y;
            --i;
            --point;
        }
    }
    ++i;
    ++point;
    for( ; i < n; ++i, ++point ) {
        x1 = x2;
        y1 = y2;
        x2 = point->x;
        y2 = point->y;
        if( x2 > domainMax ) {
            if( ( status = ptwXY_interpolatePoint( smr, ptwXY->interpolation, domainMax, &y, x1, y1, x2, y2 ) ) != nfu_Okay ) {
                smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
                return( status );
            }
            x2 = domainMax;
            y2 = y;
        }
        switch( ptwXY->interpolation ) {
        case ptwXY_interpolationFlat :
            sum += 0.5 * ( x2 - x1 ) * y1 * ( x1 + x2 );
            break;
        case ptwXY_interpolationLinLin :
            sum += ( x2 - x1 ) * ( y1 * ( 2 * x1 + x2 ) + y2 * ( x1 + 2 * x2 ) ) / 6.;
            break;
        case ptwXY_interpolationLogLin :
            inv_a1 = ( x2 - x1 ) / log( y2 / y1 );
            a1 = 1 / inv_a1;
            a1x1 = a1 * x1;
            a1x2 = a1 * x2;
            sum += inv_a1 * inv_a1 * ( exp( a1x2 ) * ( a1x2 - 1 ) - exp( a1x1 ) * ( a1x1 - 1 ) );
            break;
        default :       /* Only to stop compilers from complaining. */
            break;
        }
        if( x2 == domainMax ) break;
    }

    *value = _sign * sum;

    return( nfu_Okay );
}
/*
************************************************************
*/
nfu_status ptwXY_integrateDomainWithWeight_sqrt_x( statusMessageReporting *smr, ptwXYPoints *ptwXY, double *value ) {

    nfu_status status;
    double domainMin, domainMax;

    *value = 0.;

    if( ptwXY->status != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
        return( nfu_badSelf );
    }

    if( ptwXY->length < 2 ) return( nfu_Okay );

    if( ptwXY_domainMin( smr, ptwXY, &domainMin ) != nfu_Okay ) smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
    if( ptwXY_domainMax( smr, ptwXY, &domainMax ) != nfu_Okay ) smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
    if( ( status = ptwXY_integrateWithWeight_sqrt_x( smr, ptwXY, domainMin, domainMax, value ) ) != nfu_Okay )
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
    return( status );
}
/*
************************************************************
*/
nfu_status ptwXY_integrateWithWeight_sqrt_x( statusMessageReporting *smr, ptwXYPoints *ptwXY, double domainMin, double domainMax, 
        double *value ) {

    int64_t i, n = ptwXY->length;
    double sum = 0., x, y, x1, x2, y1, y2, _sign = 1., sqrt_x1, sqrt_x2, inv_apb, c;
    ptwXYPoint *point;
    nfu_status status;

    *value = 0.;

    if( ptwXY->status != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via." );
        return( nfu_badSelf );
    }

    if(     ( ptwXY->interpolation != ptwXY_interpolationLinLin ) &&
            ( ptwXY->interpolation != ptwXY_interpolationFlat ) ) {
        smr_setReportError2( smr, nfu_SMR_libraryID, nfu_unsupportedInterpolation,
            "Unsupported interpolation = '%s'", ptwXY->interpolationString );
        return( nfu_unsupportedInterpolation );
    }

    if( n < 2 ) return( nfu_Okay );
    if( domainMax < domainMin ) {
        x = domainMin;
        domainMin = domainMax;
        domainMax = x;
        _sign = -1.;
    }

    if( ptwXY_simpleCoalescePoints( smr, ptwXY ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
        return( nfu_Error );
    }

    for( i = 0, point = ptwXY->points; i < n; ++i, ++point ) {
        if( point->x >= domainMin ) break;
    }
    if( i == n ) return( 0. );
    x2 = point->x;
    y2 = point->y;
    if( i > 0 ) {
        if( x2 > domainMin ) {
            if( ( status = ptwXY_interpolatePoint( smr, ptwXY->interpolation, domainMin, &y, point[-1].x, point[-1].y, x2, y2 ) ) != nfu_Okay ) {
                smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
                return( status );
            }
            x2 = domainMin;
            y2 = y;
            --i;
            --point;
        }
    }
    ++i;
    ++point;
    sqrt_x2 = sqrt( x2 );
    for( ; i < n; ++i, ++point ) {
        x1 = x2;
        y1 = y2;
        sqrt_x1 = sqrt_x2;
        x2 = point->x;
        y2 = point->y;
        if( x2 > domainMax ) {
            if( ( status = ptwXY_interpolatePoint( smr, ptwXY->interpolation, domainMax, &y, x1, y1, x2, y2 ) ) != nfu_Okay ) {
                smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
                return( status );
            }
            x2 = domainMax;
            y2 = y;
        }
        sqrt_x2 = sqrt( x2 );
        inv_apb = sqrt_x1 + sqrt_x2;
        c = 2. * ( sqrt_x1 * sqrt_x2 + x1 + x2 );
        switch( ptwXY->interpolation ) {
        case ptwXY_interpolationFlat :
            sum += ( sqrt_x2 - sqrt_x1 ) * y1 * 2.5 * c;
            break;
        case ptwXY_interpolationLinLin :
            sum += ( sqrt_x2 - sqrt_x1 ) * ( y1 * ( c + x1 * ( 1. + sqrt_x2 / inv_apb ) ) + y2 * ( c + x2 * ( 1. + sqrt_x1 / inv_apb ) ) );
            break;
        default :       /* Only to stop compilers from complaining. */
            break;
        }
        if( x2 == domainMax ) break;
    }

    *value = 2. / 15. * _sign * sum;

    return( nfu_Okay );
}
/*
************************************************************
*/
ptwXPoints *ptwXY_groupOneFunction( statusMessageReporting *smr, ptwXYPoints *ptwXY, ptwXPoints *groupBoundaries, 
        ptwXY_group_normType normType, ptwXPoints *ptwX_norm ) {

    int64_t i, igs, ngs;
    double x1, y1, x2, y2, y2p, xg1, xg2, sum;
    ptwXYPoints *f;
    ptwXPoints *groupedData = NULL;

    if( ptwXY_simpleCoalescePoints( smr, ptwXY ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
        return( NULL );
    }
    if( groupBoundaries->status != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via: groupBoundaries." );
        return( NULL );
    }
    if( ptwXY->interpolation == ptwXY_interpolationOther ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_otherInterpolation, "Other interpolation not supported for integration." );
        return( NULL );
    }

    ngs = ptwX_length( smr, groupBoundaries ) - 1;
    if( normType == ptwXY_group_normType_norm ) {
        if( ptwX_norm == NULL ) {
            smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badNorm, "Norm function required but is NULL." );
            return( NULL );
        }
        if( ptwX_norm->status != nfu_Okay ) {
            smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via: norm." );
            return( NULL );
        }
        if( ptwX_length( smr, ptwX_norm ) != ngs ) {
            smr_setReportError2( smr, nfu_SMR_libraryID, nfu_badNorm, "Norm length = %d but there are %d groups.",
                    (int) ptwX_length( NULL, ptwX_norm ), (int) ngs );
            return( NULL );
        }
    }

    if( ( f = ptwXY_intersectionWith_ptwX( smr, ptwXY, groupBoundaries ) ) == NULL ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
        return( NULL );
    }
    if( f->length == 0 ) {
        groupedData = ptwX_createLine( smr, ngs, ngs, 0, 0 );
        if( groupedData == NULL ) smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
        return( groupedData );
    }

    if( ( groupedData = ptwX_new( smr, ngs ) ) == NULL ) goto Err;
    xg1 = groupBoundaries->points[0];
    x1 = f->points[0].x;
    y1 = f->points[0].y;
    for( igs = 0, i = 1; igs < ngs; igs++ ) {
        xg2 = groupBoundaries->points[igs+1];
        sum = 0;
        if( xg2 > x1 ) {
            for( ; i < f->length; i++, x1 = x2, y1 = y2 ) {
                x2 = f->points[i].x;
                if( x2 > xg2 ) break;
                y2p = y2 = f->points[i].y;
                if( f->interpolation == ptwXY_interpolationFlat ) y2p = y1;
                sum += ( y1 + y2p ) * ( x2 - x1 );
            }
        }
        if( sum != 0. ) {
            if( normType == ptwXY_group_normType_dx ) {
                sum /= ( xg2 - xg1 ); }
            else if( normType == ptwXY_group_normType_norm ) {
                if( ptwX_norm->points[igs] == 0. ) {
                    smr_setReportError2( smr, nfu_SMR_libraryID, nfu_divByZero, "Divide by 0. Norm at index %d is 0.", (int) igs );
                    goto Err;
                }
                sum /= ptwX_norm->points[igs];
            }
        }
        groupedData->points[igs] = 0.5 * sum;
        groupedData->length++;
        xg1 = xg2;
    }

    ptwXY_free( f );
    return( groupedData );

Err:
    smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
    ptwXY_free( f );
    if( groupedData != NULL ) ptwX_free( groupedData );
    return( NULL );
}
/*
************************************************************
*/
ptwXPoints *ptwXY_groupTwoFunctions( statusMessageReporting *smr, ptwXYPoints *ptwXY1, ptwXYPoints *ptwXY2, 
        ptwXPoints *groupBoundaries, ptwXY_group_normType normType, ptwXPoints *ptwX_norm ) {

    int64_t i, igs, ngs;
    double x1, fy1, gy1, x2, fy2, gy2, fy2p, gy2p, xg1, xg2, sum;
    ptwXYPoints *f = NULL, *ff, *g = NULL, *gg = NULL;
    ptwXPoints *groupedData = NULL;

    if( ptwXY_simpleCoalescePoints( smr, ptwXY1 ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via: source1." );
        return( NULL );
    }
    if( ptwXY_simpleCoalescePoints( smr, ptwXY2 ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via: source2." );
        return( NULL );
    }
    if( groupBoundaries->status != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via: groupBoundaries." );
        return( NULL );
    }

    if( ptwXY1->interpolation == ptwXY_interpolationOther ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_otherInterpolation, 
                "Other interpolation not supported for integration: source1." );
        return( NULL );
    }
    if( ptwXY2->interpolation == ptwXY_interpolationOther ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_otherInterpolation, 
                "Other interpolation not supported for integration: source2." );
        return( NULL );
    }

    ngs = ptwX_length( smr, groupBoundaries ) - 1;
    if( normType == ptwXY_group_normType_norm ) {
        if( ptwX_norm == NULL ) {
            smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badNorm, "Norm function required but is NULL." );
            return( NULL );
        }
        if( ptwX_norm->status != nfu_Okay ) {
            smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via: norm." );
            return( NULL );
        }
        if( ptwX_length( smr, ptwX_norm ) != ngs ) {
            smr_setReportError2( smr, nfu_SMR_libraryID, nfu_badNorm, "Norm length = %d but there are %d groups.",
                    (int) ptwX_length( NULL, ptwX_norm ), (int) ngs );
            return( NULL );
        }
    }

    if( ( ff = ptwXY_intersectionWith_ptwX( smr, ptwXY1, groupBoundaries ) ) == NULL ) goto Err;
    if( ( gg = ptwXY_intersectionWith_ptwX( smr, ptwXY2, groupBoundaries ) ) == NULL ) goto Err;
    if( ( ff->length == 0 ) || ( gg->length == 0 ) ) {
        ptwXY_free( ff );
        ptwXY_free( gg );
        groupedData = ptwX_createLine( smr, ngs, ngs, 0, 0 );
        if( groupedData == NULL ) smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
        return( groupedData );
    }

    if( ptwXY_tweakDomainsToMutualify( smr, ff, gg, 4, 0 ) != nfu_Okay ) goto Err;
    if( ( f = ptwXY_union( smr, ff, gg, ptwXY_union_fill ) ) == NULL ) goto Err;
    if( ( g = ptwXY_union( smr, gg, f,  ptwXY_union_fill ) ) == NULL ) goto Err;

    if( ( groupedData = ptwX_new( smr, ngs ) ) == NULL ) goto Err;
    xg1 = groupBoundaries->points[0];
    x1 = f->points[0].x;
    fy1 = f->points[0].y;
    gy1 = g->points[0].y;
    for( igs = 0, i = 1; igs < ngs; igs++ ) {
        xg2 = groupBoundaries->points[igs+1];
        sum = 0;
        if( xg2 > x1 ) {
            for( ; i < f->length; i++, x1 = x2, fy1 = fy2, gy1 = gy2 ) {
                x2 = f->points[i].x;
                if( x2 > xg2 ) break;
                fy2p = fy2 = f->points[i].y;
                if( f->interpolation == ptwXY_interpolationFlat ) fy2p = fy1;
                gy2p = gy2 = g->points[i].y;
                if( g->interpolation == ptwXY_interpolationFlat ) gy2p = gy1;
                sum += ( ( fy1 + fy2p ) * ( gy1 + gy2p ) + fy1 * gy1 + fy2p * gy2p ) * ( x2 - x1 );
            }
        }
        if( sum != 0. ) {
            if( normType == ptwXY_group_normType_dx ) {
                sum /= ( xg2 - xg1 ); }
            else if( normType == ptwXY_group_normType_norm ) {
                if( ptwX_norm->points[igs] == 0. ) {
                    smr_setReportError2( smr, nfu_SMR_libraryID, nfu_divByZero, "Divide by 0. Norm at index %d is 0.", (int) igs );
                    goto Err;
                }
                sum /= ptwX_norm->points[igs];
            }
        }
        groupedData->points[igs] = sum / 6.;
        groupedData->length++;
        xg1 = xg2;
    }

    ptwXY_free( f );
    ptwXY_free( g );
    ptwXY_free( ff );
    ptwXY_free( gg );
    return( groupedData );

Err:
    smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
    if( ff != NULL ) ptwXY_free( ff );
    if( gg != NULL ) ptwXY_free( gg );
    if( f != NULL ) ptwXY_free( ff );
    if( g != NULL ) ptwXY_free( g );
    if( groupedData != NULL ) ptwX_free( groupedData );
    return( NULL );
}
/*
************************************************************
*/
ptwXPoints *ptwXY_groupThreeFunctions( statusMessageReporting *smr, ptwXYPoints *ptwXY1, ptwXYPoints *ptwXY2, 
        ptwXYPoints *ptwXY3, ptwXPoints *groupBoundaries, ptwXY_group_normType normType, ptwXPoints *ptwX_norm ) {

    int64_t i, igs, ngs;
    double x1, fy1, gy1, hy1, x2, fy2, gy2, hy2, fy2p, gy2p, hy2p, xg1, xg2, sum;
    ptwXYPoints *f = NULL, *ff, *fff = NULL, *g = NULL, *gg = NULL, *h = NULL, *hh = NULL;
    ptwXPoints *groupedData = NULL;

    if( ptwXY_simpleCoalescePoints( smr, ptwXY1 ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via: source1." );
        return( NULL );
    }
    if( ptwXY_simpleCoalescePoints( smr, ptwXY2 ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via: source2." );
        return( NULL );
    }
    if( ptwXY_simpleCoalescePoints( smr, ptwXY3 ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via: source3." );
        return( NULL );
    }
    if( groupBoundaries->status != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via: groupBoundaries." );
        return( NULL );
    }

    if( ptwXY1->interpolation == ptwXY_interpolationOther ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_otherInterpolation, "Other interpolation not supported for integration: source1." );
        return( NULL );
    }
    if( ptwXY2->interpolation == ptwXY_interpolationOther ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_otherInterpolation, "Other interpolation not supported for integration: source2." );
        return( NULL );
    }
    if( ptwXY3->interpolation == ptwXY_interpolationOther ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_otherInterpolation, "Other interpolation not supported for integration: source3." );
        return( NULL );
    }

    ngs = ptwX_length( smr, groupBoundaries ) - 1;
    if( normType == ptwXY_group_normType_norm ) {
        if( ptwX_norm == NULL ) {
            smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badNorm, "Norm function required but is NULL." );
            return( NULL );
        }
        if( ptwX_norm->status != nfu_Okay ) {
            smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_badSelf, "Via: norm." );
            return( NULL );
        }
        if( ptwX_length( smr, ptwX_norm ) != ngs ) {
            smr_setReportError2( smr, nfu_SMR_libraryID, nfu_badNorm, "Norm length = %d but there are %d groups.",
                    (int) ptwX_length( NULL, ptwX_norm ), (int) ngs );
            return( NULL );
        }
    }

    if( ( ff = ptwXY_intersectionWith_ptwX( smr, ptwXY1, groupBoundaries ) ) == NULL ) goto Err;
    if( ( gg = ptwXY_intersectionWith_ptwX( smr, ptwXY2, groupBoundaries ) ) == NULL ) goto Err;
    if( ( hh = ptwXY_intersectionWith_ptwX( smr, ptwXY3, groupBoundaries ) ) == NULL ) goto Err;
    if( ( ff->length == 0 ) || ( gg->length == 0 ) || ( hh->length == 0 ) ) {
        ptwXY_free( ff );
        ptwXY_free( gg );
        ptwXY_free( hh );
        groupedData = ptwX_createLine( smr, ngs, ngs, 0, 0 );
        if( groupedData == NULL ) smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
        return( groupedData );
    }

    if( ptwXY_tweakDomainsToMutualify( smr, ff, gg, 4, 0 ) != nfu_Okay ) goto Err;
    if( ptwXY_tweakDomainsToMutualify( smr, ff, hh, 4, 0 ) != nfu_Okay ) goto Err;
    if( ptwXY_tweakDomainsToMutualify( smr, gg, hh, 4, 0 ) != nfu_Okay ) goto Err;
    if( ( fff = ptwXY_union( smr,  ff,  gg, ptwXY_union_fill ) ) == NULL ) goto Err;
    if( (   h = ptwXY_union( smr,  hh, fff, ptwXY_union_fill ) ) == NULL ) goto Err;
    if( (   f = ptwXY_union( smr, fff,   h, ptwXY_union_fill ) ) == NULL ) goto Err;
    if( (   g = ptwXY_union( smr,  gg,   h, ptwXY_union_fill ) ) == NULL ) goto Err;

    if( ( groupedData = ptwX_new( smr, ngs ) ) == NULL ) goto Err;
    xg1 = groupBoundaries->points[0];
    x1 = f->points[0].x;
    fy1 = f->points[0].y;
    gy1 = g->points[0].y;
    hy1 = h->points[0].y;
    for( igs = 0, i = 1; igs < ngs; igs++ ) {
        xg2 = groupBoundaries->points[igs+1];
        sum = 0;
        if( xg2 > x1 ) {
            for( ; i < f->length; i++, x1 = x2, fy1 = fy2, gy1 = gy2, hy1 = hy2 ) {
                x2 = f->points[i].x;
                if( x2 > xg2 ) break;
                fy2p = fy2 = f->points[i].y;
                if( f->interpolation == ptwXY_interpolationFlat ) fy2p = fy1;
                gy2p = gy2 = g->points[i].y;
                if( g->interpolation == ptwXY_interpolationFlat ) gy2p = gy1;
                hy2p = hy2 = h->points[i].y;
                if( h->interpolation == ptwXY_interpolationFlat ) hy2p = hy1;
                sum += ( ( fy1 + fy2p ) * ( gy1 + gy2p ) * ( hy1 + hy2p ) + 2 * fy1 * gy1 * hy1 + 2 * fy2p * gy2p * hy2p ) * ( x2 - x1 );
            }
        }
        if( sum != 0. ) {
            if( normType == ptwXY_group_normType_dx ) {
                sum /= ( xg2 - xg1 ); }
            else if( normType == ptwXY_group_normType_norm ) {
                if( ptwX_norm->points[igs] == 0. ) {
                    smr_setReportError2( smr, nfu_SMR_libraryID, nfu_divByZero, "Divide by 0. Norm at index %d is 0.", (int) igs );
                    goto Err;
                }
                sum /= ptwX_norm->points[igs];
            }
        }
        groupedData->points[igs] = sum / 12.;
        groupedData->length++;
        xg1 = xg2;
    }

    ptwXY_free( f );
    ptwXY_free( g );
    ptwXY_free( h );
    ptwXY_free( ff );
    ptwXY_free( gg );
    ptwXY_free( hh );
    ptwXY_free( fff );
    return( groupedData );

Err:
    smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
    if( fff != NULL ) ptwXY_free( fff );
    if( ff != NULL ) ptwXY_free( ff );
    if( gg != NULL ) ptwXY_free( gg );
    if( hh != NULL ) ptwXY_free( hh );
    if( f != NULL ) ptwXY_free( f );
    if( g != NULL ) ptwXY_free( g );
    if( h != NULL ) ptwXY_free( h );
    if( groupedData != NULL ) ptwX_free( groupedData );
    return( NULL );
}
/*
************************************************************
*/
ptwXPoints *ptwXY_runningIntegral( statusMessageReporting *smr, ptwXYPoints *ptwXY ) {

    int i;
    ptwXPoints *runningIntegral = NULL;
    double integral = 0., sum;

    if( ptwXY_simpleCoalescePoints( smr, ptwXY ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
        return( NULL );
    }

    if( ( runningIntegral = ptwX_new( smr, ptwXY->length ) ) == NULL ) goto Err;

    if( ptwX_setPointAtIndex( smr, runningIntegral, 0, 0. ) != nfu_Okay ) goto Err;
    for( i = 1; i < ptwXY->length; i++ ) {
        if( ptwXY_f_integrate( smr, ptwXY->interpolation, ptwXY->points[i-1].x, ptwXY->points[i-1].y, 
            ptwXY->points[i].x, ptwXY->points[i].y, &sum ) != nfu_Okay ) goto Err;
        integral += sum;
        if( ptwX_setPointAtIndex( smr, runningIntegral, i, integral ) != nfu_Okay ) goto Err;
    }
    return( runningIntegral );

Err:
    smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
    if( runningIntegral != NULL ) ptwX_free( runningIntegral );
    return( NULL );
}
/*
************************************************************
*/
nfu_status ptwXY_integrateWithFunction( statusMessageReporting *smr, ptwXYPoints *ptwXY, ptwXY_createFromFunction_callback func, 
        void *argList, double domainMin, double domainMax, int degree, int recursionLimit, double tolerance, double *value ) {

    int64_t i1, i2, n1 = ptwXY->length;
    long evaluations;
    double integral = 0., integral_, sign = -1., xa, xb;
    ptwXY_integrateWithFunctionInfo integrateWithFunctionInfo;
    ptwXYPoint *point;
    nfu_status status;

    if( ptwXY_simpleCoalescePoints( smr, ptwXY ) != nfu_Okay ) {
        smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via." );
        return( nfu_Error );
    }

    if( domainMin == domainMax ) return( 0. );
    if( n1 < 2 ) return( 0. );

    if( domainMin > domainMax ) {
        sign = domainMin;
        domainMin = domainMax;
        domainMax = sign;
        sign = -1.;
    }
    if( domainMin >= ptwXY->points[n1-1].x ) return( 0. );
    if( domainMax <= ptwXY->points[0].x ) return( 0. );

    for( i1 = 0; i1 < ( n1 - 1 ); i1++ ) {
        if( ptwXY->points[i1+1].x > domainMin ) break;
    }
    for( i2 = n1 - 1; i2 > i1; i2-- ) {
        if( ptwXY->points[i2-1].x < domainMax ) break;
    }
    point = &(ptwXY->points[i1]);

    integrateWithFunctionInfo.degree = degree;
    integrateWithFunctionInfo.func = func;
    integrateWithFunctionInfo.argList = argList;
    integrateWithFunctionInfo.interpolation = ptwXY->interpolation;
    integrateWithFunctionInfo.x2 = point->x;
    integrateWithFunctionInfo.y2 = point->y;

    xa = domainMin;
    for( ; i1 < i2; i1++ ) {
        integrateWithFunctionInfo.x1 = integrateWithFunctionInfo.x2;
        integrateWithFunctionInfo.y1 = integrateWithFunctionInfo.y2;
        ++point;
        integrateWithFunctionInfo.x2 = point->x;
        integrateWithFunctionInfo.y2 = point->y;
        xb = point->x;
        if( xb > domainMax ) xb = domainMax;
        status = nf_GnG_adaptiveQuadrature( ptwXY_integrateWithFunction2, ptwXY_integrateWithFunction3, &integrateWithFunctionInfo,
            xa, xb, recursionLimit, tolerance, &integral_, &evaluations );
        if( status != nfu_Okay ) {
            smr_setReportError2p( smr, nfu_SMR_libraryID, nfu_Error, "Via. Error from nf_GnG_adaptiveQuadrature." );
            return( status );
        }
        integral += integral_;
        xa = xb;
    }
    *value = integral;

    return( nfu_Okay );
}
/*
************************************************************
*/
static nfu_status ptwXY_integrateWithFunction2( nf_Legendre_GaussianQuadrature_callback integrandFunction, void *argList, double x1,
        double x2, double *integral ) {

    ptwXY_integrateWithFunctionInfo *integrateWithFunctionInfo = (ptwXY_integrateWithFunctionInfo *) argList;
    nfu_status status;

    status = nf_Legendre_GaussianQuadrature( integrateWithFunctionInfo->degree, x1, x2, integrandFunction, argList, integral );
    return( status );
}
/*
************************************************************
*/
static nfu_status ptwXY_integrateWithFunction3( double x, double *y, void *argList ) {

    double yf;
    ptwXY_integrateWithFunctionInfo *integrateWithFunctionInfo = (ptwXY_integrateWithFunctionInfo *) argList;
    nfu_status status;

    if( ( status = ptwXY_interpolatePoint( NULL, integrateWithFunctionInfo->interpolation, x, &yf, 
            integrateWithFunctionInfo->x1, integrateWithFunctionInfo->y1, 
            integrateWithFunctionInfo->x2, integrateWithFunctionInfo->y2 ) ) == nfu_Okay ) {
        status = integrateWithFunctionInfo->func( NULL, x, y, integrateWithFunctionInfo->argList );
        *y *= yf;
    }
    return( status );
}
