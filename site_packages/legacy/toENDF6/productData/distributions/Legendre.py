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

import fudge.gnd.productData.distributions.Legendre as LegendreModule
import site_packages.legacy.toENDF6.gndToENDF6 as gndToENDF6Module
import site_packages.legacy.toENDF6.endfFormats as endfFormatsModule

#
# form
#
def toENDF6( self, MT, endfMFList, flags, targetInfo ) :

    self.LegendreSubform.toENDF6( MT, endfMFList, flags, targetInfo )

LegendreModule.form.toENDF6 = toENDF6

#
# pointwise
#
def toENDF6( self, MT, endfMFList, flags, targetInfo ) :

    EInInterpolation = gndToENDF6Module.axisToEndfInterpolationFlag( self.axes[0] )
    independent, dependent, qualifier = self.axes[1].interpolation.getInterpolationTokens( )
    if( dependent == standardsModule.interpolation.flatToken ) :
        LEP = 1  # interpolation for Eout
    else :
        LEP = 2
    ENDFDataList = [ endfFormatsModule.endfContLine( 0, 0, 1, LEP, 1, len( self ) ) ]
    ENDFDataList += endfFormatsModule.endfInterpolationList( [ len( self ), EInInterpolation ] )
    for energy_in in self :
        NA, data = 0, []
        for w_xys_LegendreSeries in energy_in :
            NA = max( len( w_xys_LegendreSeries) , NA )
            data += [ w_xys_LegendreSeries.value ] + w_xys_LegendreSeries.coefficients
        ENDFDataList.append( endfFormatsModule.endfContLine( 0, energy_in.value, 0, NA - 1, len( data ), len( data ) / ( NA + 1 ) ) )
        ENDFDataList += endfFormatsModule.endfDataList( data )
    LAW = 1
    gndToENDF6Module.toENDF6_MF6( MT, endfMFList, flags, targetInfo, LAW, self.productFrame, ENDFDataList )

LegendreModule.pointwise.toENDF6 = toENDF6

#
# LLNLPointwise
#
def toENDF6( self, MT, endfMFList, flags, targetInfo ) :

    LAW, LEP = 1, 2
    EInInterpolation = gndToENDF6Module.axisToEndfInterpolationFlag( self.axes[1] )
    E_ins = [ [ EpCl.value, {} ] for EpCl in self[0].EpP ]
    for l_EEpCl in self :
        for indexE, EpCl in enumerate( l_EEpCl ) :
            if( EpCl.value != E_ins[indexE][0] ) :
                raise Exception( "E_in = %s not in list E_ins" % EpCl.value )
            for Ep, Cl in EpCl :
                if( Ep not in E_ins[indexE][1] ) :
                    E_ins[indexE][1][Ep] = []
                    for l in xrange( l_EEpCl.l ) : E_ins[indexE][1][Ep].append( 0. )
                E_ins[indexE][1][Ep].append( Cl )
    ENDFDataList = [ endfFormatsModule.endfContLine( 0, 0, 1, LEP, 1, len( E_ins ) ) ]
    ENDFDataList += endfFormatsModule.endfInterpolationList( [ len( E_ins ), EInInterpolation ] )
    for Es in E_ins :
        NA, data = 0, []
        for key in sorted( Es[1] ) :
            LegendreSeries = Es[1][key]
            NA = max( len( LegendreSeries ) , NA )
            data += [ key ] + LegendreSeries
        ENDFDataList.append( endfFormatsModule.endfContLine( 0, Es[0], 0, NA - 1, len( data ), len( data ) / ( NA + 1 ) ) )
        ENDFDataList += endfFormatsModule.endfDataList( data )
    gndToENDF6Module.toENDF6_MF6( MT, endfMFList, flags, targetInfo, LAW, self.productFrame, ENDFDataList )

LegendreModule.LLNLPointwise.toENDF6 = toENDF6
