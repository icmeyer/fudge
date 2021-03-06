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

from fudge.core.utilities import brb
import fudge.gnd.productData.distributions.energyAngular as energyAngularModule

import site_packages.legacy.toENDF6.endfFormats as endfFormatsModule
import site_packages.legacy.toENDF6.gndToENDF6 as gndToENDF6Module
import xData.multiD_XYs as multiD_XYsModule
import xData.series1d as series1dModule
import pqu.PQU as PQUModule

#
# form
#
def toENDF6( self, MT, endfMFList, flags, targetInfo ) :

    subform = self.energyAngularSubform
    frame = self.productFrame
    if( hasattr( subform, 'toENDF6' ) ) :
        LAW, MF6 = subform.toENDF6( flags, targetInfo )
        gndToENDF6Module.toENDF6_MF6( MT, endfMFList, flags, targetInfo, LAW, frame, MF6 )
    else :
        print 'WARNING: energyAngular subform "%s" has no toENDF6 method' % subform.moniker

energyAngularModule.form.toENDF6 = toENDF6

#
# XYs3d
#
def toENDF6( self, flags, targetInfo ) :

    MT = 5
    EInInterpolation = gndToENDF6Module.gndToENDF2PlusDInterpolationFlag( self.interpolation, self.interpolationQualifier )
    EpInterpolation0 = gndToENDF6Module.gndToENDF2PlusDInterpolationFlag( self[0].interpolation, self[0].interpolationQualifier )
    if( EpInterpolation0 == 1 ) :       # flat interpolation
        LEP = 1
    elif( EpInterpolation0 == 2 ) :     # lin-lin interpolation
        LEP = 2
    else :
        raise 'hell - fix me'
    ENDFDataList = [ endfFormatsModule.endfContLine( 0, 0, 1, LEP, 1, len( self ) ) ]
    ENDFDataList += endfFormatsModule.endfInterpolationList( [ len( self ), EInInterpolation ] )
    energyInFactor = PQUModule.PQU( 1, self.axes[3].unit ).getValueAs( 'eV' )
    energyPFactor = PQUModule.PQU( 1, self.axes[2].unit ).getValueAs( 'eV' )
    for energyIn in self :
        if( not( isinstance( energyIn, multiD_XYsModule.XYs2d ) ) ) : raise 'hell - fix me'
        EpInterpolation = gndToENDF6Module.gndToENDF2PlusDInterpolationFlag( energyIn.interpolation, energyIn.interpolationQualifier )
        if( EpInterpolation != EpInterpolation0 ) : raise 'hell - fix me'
        NA, data = 0, []
        for energy_p in energyIn :
            if( not( isinstance( energy_p, series1dModule.LegendreSeries ) ) ) : raise 'hell - fix me'
            NA = max( len( energy_p ) , NA )
            coefficients = [ coefficient / energyPFactor for coefficient in energy_p ]
            data += [ energy_p.value * energyPFactor ] + coefficients
        ENDFDataList.append( endfFormatsModule.endfContLine( 0, energyIn.value * energyInFactor, 0, NA - 1, len( data ), len( data ) / ( NA + 1 ) ) )
        ENDFDataList += endfFormatsModule.endfDataList( data )
    LAW = 1
    return( LAW, ENDFDataList )

energyAngularModule.XYs3d.toENDF6 = toENDF6
