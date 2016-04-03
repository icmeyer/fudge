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

class endlReactionParameters :
    """This class contains the parameters C, S, X1, X2, X3, X4, Q for a reaction."""

    def __init__( self, C, S, X1, X2, X3, X4, Q ) :
        """Creates a new endlReactionParameters object."""

        self.C = C
        self.S = S
        self.X1 = X1
        self.X2 = X2
        self.X3 = X3
        self.X4 = X4
        self.Q = Q

    def __repr__( self ) :
        """Creates a string of self."""

        s = "C = %2d, S = %3d, X1 = %14.7e, X2 = %14.7e, X3 = %14.7e, X4 = %14.7e, Q = %14.7e" \
            % ( self.C, self.S, self.X1, self.X2, self.X3, self.X4, self.Q )
        return( s )

    def __getitem__( self, index ) :

        if( type( index ) == type( '' ) ) :
            if( index == 'C' ) : return( self.C )
            if( index == 'S' ) : return( self.S )
            if( index == 'X1' ) : return( self.X1 )
            if( index == 'X2' ) : return( self.X2 )
            if( index == 'X3' ) : return( self.X3 )
            if( index == 'X4' ) : return( self.X4 )
            if( index == 'Q' ) : return( self.Q )
            raise Exception( 'invalid string index = %s' % index )
        elif( type( index ) == type( 0 ) ) :
            if( index == 0 ) : return( self.C )
            if( index == 1 ) : return( self.S )
            if( index == 2 ) : return( self.X1 )
            if( index == 3 ) : return( self.X2 )
            if( index == 4 ) : return( self.X3 )
            if( index == 5 ) : return( self.X4 )
            if( index == 6 ) : return( self.Q )
            raise Exception( 'invalid integer index = %d' % index )
        raise Exception( 'invalid index type = %s; index must be string or integer' % type( index ) )

    def toPythonList( self ) :
        """Returns the [ self.C, self.S, self.X1, self.X2, self.X3, self.X4, self.Q ]"""

        return( [ self.C, self.S, self.X1, self.X2, self.X3, self.X4, self.Q ] )
