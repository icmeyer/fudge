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

__metaclass__ = type

from . import standards as standardsModule
from . import base as baseModule
from . import axes as axesModule
from . import array as arrayModule

class gridded( baseModule.xDataFunctional ) :

    moniker = 'gridded'

    def __init__( self, axes, array,
            index = None, valueType = standardsModule.types.float64Token, value = None, label = None ) :

        for axis in axes :
            if( axis.index == 0 ) :
                if( not( isinstance( axis, axesModule.axis ) ) ) : raise Exception( 'dependent axis must not have a grid' )
            else :
                if( not( isinstance( axis, axesModule.grid ) ) ) : raise Exception( 'independent axis must have a grid' )
        if( not( isinstance( array, arrayModule.arrayBase ) ) ) : raise TypeError( 'array not value type' )

        baseModule.xDataFunctional.__init__( self, self.moniker, len( array ), axes, index = index, valueType = valueType,
                value = value, label = label )

        self.array = array
        self.array.setAncestor( self )

    def __len__( self ) :
        """Returns the number of regions in self."""

        return( len( self.array ) )

    def copy( self ):

        return gridded( self.axes.copy( ), self.array.copy( ), index = self.index, valueType = self.valueType, label = self.label )

    __deepcopy__ = __copy__ = copy

    def getGrid( self, index ) :

        if( 0 < index <= len( self ) ) : return( self.axes[index].grid )
        raise IndexError( 'index = %d out of range [1,%s]' % len( self ) )

    def getGridUnit( self, index ) :

        return( self.axes[index].unit )

    def toXMLList( self, indent = '', **kwargs ) :

        indent2 = indent + kwargs.get( 'incrementalIndent', '  ' )

        attributeStr = baseModule.xDataFunctional.attributesToXMLAttributeStr( self )
        XMLList = [ '%s<%s dimension="%s"%s>' % ( indent, self.moniker, self.dimension, attributeStr ) ]
        XMLList += self.axes.toXMLList( indent2, **kwargs )
        XMLList += self.array.toXMLList( indent2, **kwargs )
        XMLList[-1] += '</%s>' % self.moniker
        return( XMLList )

    @classmethod
    def parseXMLNode( cls, element, xPath, linkData, **kwargs ) :

        xPath.append( element.tag )

        axes = None
        if element.find('axes') is not None:
            axes = axesModule.axes.parseXMLNode( element.find('axes'), xPath, linkData )
        array = arrayModule.arrayBase.parseXMLNode( element[1], xPath, linkData )
        index = int( element.get('index') ) if 'index' in element.keys() else None
        value = float( element.get('value') ) if 'value' in element.keys() else None
        Grid = gridded( axes, array, index=index, value=value, label=element.get('label') )
        xPath.pop( )
        return Grid
