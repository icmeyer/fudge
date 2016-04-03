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

"""A covarianceSuite is organized into sections, where each section contains either
    - a covariance matrix for a single reaction quantity (cross section, multiplicity, etc), or
    - a covariance matrix between two different quantities (off-diagonal block)
    """
from xData.ancestry import ancestry
from xData import link as linkModule
from fudge.gnd import suites
from . import covarianceMatrix
from .mixed import mixedForm
from .summed import summedCovariance
from .distributions import LegendreOrderCovarianceForm
from pqu import PQU as PQUModule

__metaclass__ = type

class section( suites.suite ):
    """
    A covarianceSuite contains sections, where each section represents either a self-covariance for one quantity,
    or a cross-covariance between two quantities

    More generally, the covarianceSuite can be thought of as a single covariance matrix with all covariance data
    for a target/projectile. It is broken into sections, where each section holds a chunk of the full matrix.

    Within each section, covariance data can take multiple forms: :py:class:`covarianceMatrix` is the most common,
    but 'summed', 'mixed' are also possible. 

    Valid values in the :py:attr:`forms` dictionary are:
        * mixedForm
        * summedCovariance
        * LegendreOrderCovarianceForm
        * covarianceMatrix
    """

    moniker = 'section'

    def __init__(self, label=None, id=None, rowData=None, columnData=None):
        """ each section needs a unique id, pointers to the central values (row and column),
        and one or more forms """

        suites.suite.__init__( self, [covarianceMatrix, mixedForm, summedCovariance, LegendreOrderCovarianceForm] )
        self.label = label #: a str label that gets used on plots, etc.
        self.id = id #: a str identifier, useful for resolving links
        self.rowData = rowData #: xData.link.link pointing to the corresponding data for the covariance row
        self.columnData = columnData #: xData.link.link pointing to the corresponding data for the covariance column

    def check( self, info ):
        """ check each section """

        from fudge.gnd import warning
        warnings = []
        for form in self:
            formWarnings = form.check( info )
            if formWarnings:
                warnings.append( warning.context( "Form '%s':" % form.label, formWarnings ) )

        return warnings
    
    def fix( self, **kw ): 
        """assemble some useful info, to be handed down to children's check() functions"""
        info = {}
        warnings = []
        if self.rowData is None:    info['rowENDF_MFMT'] = None
        else:                       info['rowENDF_MFMT'] = self.rowData['ENDF_MFMT']
        if self.columnData is None: info['columnENDF_MFMT'] = None
        else:                       info['columnENDF_MFMT'] = self.columnData['ENDF_MFMT']
        info.update( kw )
        for form in self: warnings += form.fix( **info )
        return warnings

    def toXMLList( self, indent = '', **kwargs ) :

        indent2 = indent + kwargs.get( 'incrementalIndent', '  ' )

        xmlString = [indent+'<%s label="%s" id="%s"' % (self.moniker, self.label, self.id)]
        if self.columnData is not None: xmlString[0] += ' crossTerm="true"'
        xmlString[0] += '>'
        for dataPointer in ('rowData','columnData'):
            if getattr(self, dataPointer) is not None:
                xmlString.append( getattr(self, dataPointer).toXML( indent2, **kwargs ) )
        for form in self:
            xmlString += form.toXMLList( indent2, **kwargs )
        xmlString[-1] += '</%s>' % self.moniker
        return xmlString

    @classmethod
    def parseXMLNode( cls, element, xPath, linkData ):
        """Translate <section> element from xml."""

        xPath.append( '%s[@id="%s"]' % (element.tag, element.get('id') ) )
        linkData['typeConversion'] = {'incidentEnergyLowerBound':PQUModule.PQU, 'incidentEnergyUpperBound':PQUModule.PQU}
        rowData_ = rowData.parseXMLNode( element[0], xPath, linkData )
        columnData_ = None
        if element[1].tag=="columnData":
            columnData_ = columnData.parseXMLNode( element[1], xPath, linkData )
        del linkData['typeConversion']
        section_ = section( element.get('label'), element.get('id'), rowData_, columnData_ )
        start = 2 if (columnData_ is not None) else 1
        for form in element[start:]:
            formClass = {
                    covarianceMatrix.moniker: covarianceMatrix,
                    mixedForm.moniker: mixedForm,
                    summedCovariance.moniker: summedCovariance,
                    LegendreOrderCovarianceForm.moniker: LegendreOrderCovarianceForm,
                    }.get( form.tag )
            if formClass is None:
                raise Exception("encountered unknown covariance matrix form '%s'" % form.tag)
            section_.add( formClass.parseXMLNode( form, xPath, linkData ) )
        xPath.pop()
        return section_

class rowData( linkModule.link ):

    moniker = 'rowData'

class columnData( linkModule.link ):

    moniker = 'columnData'

class reactionSum( ancestry ):
    """ 
    A single covariance matrix is often given for a sum (or 'lump') of several reaction channels.
    Define the sum here, then in the covariance <section>, refer to this summed reaction   
    """

    moniker = 'reactionSum'

    def __init__(self, id=None, reactions=None, ENDF_MFMT=None):

        ancestry.__init__( self )
        self.id = id #: an identifier str
        self.reactions = reactions or [] #: a list of xData.link.link's that point to the reactions that are lumped together
        self.ENDF_MFMT = ENDF_MFMT #: the ENDF MF & MT values, a tuple of form (MF, MT)

    def toXMLList( self, indent = '', **kwargs ) :

        indent2 = indent + kwargs.get( 'incrementalIndent', '  ' )

        xmlString = [ '%s<reactionSum id="%s" ENDF_MFMT="%d,%d">' % ( indent, self.id, self.ENDF_MFMT[0], self.ENDF_MFMT[1] ) ]
        for ch in self.reactions:
            xmlString.append( ch.toXML( indent2, **kwargs ) )
        xmlString[-1] += '</reactionSum>'
        return xmlString

    @staticmethod
    def parseXMLNode( element, xPath, linkData ):
        """Translate <reactionSum> element from xml."""

        xPath.append( '%s[@id="%s"]' % (element.tag, element.get('id') )  )
        rsum = reactionSum( **dict(element.items()) )
        rsum.ENDF_MFMT = map(int, rsum.ENDF_MFMT.split(','))
        for child in element:
            link_ = rowData.parseXMLNode( child, xPath, linkData )
            linkData['unresolvedLinks'].append( link_ )
            rsum.reactions.append( link_ )
        xPath.pop()
        return rsum

class externalReaction( ancestry ):
    """ 
    Covariance may relate this target with another material ('cross-material covariance'). In this case,
    specify the other material and reaction here 
    """

    moniker = 'externalReaction'

    def __init__(self, id=None, target=None, ENDF_MFMT=None):

        ancestry.__init__( self )
        self.id = id #: an identifier str
        self.target=target #: the name of the target isotope/evaluation
        self.ENDF_MFMT = ENDF_MFMT #: the ENDF MF & MT values, a tuple of form (MF, MT) 

    def toXMLList( self, indent = '', **kwargs ) :

        xmlString = [ '%s<externalReaction id="%s" target="%s" ENDF_MFMT="%d,%d"/>' % \
                ( indent, self.id, self.target, self.ENDF_MFMT[0], self.ENDF_MFMT[1] ) ]
        return xmlString

    @staticmethod
    def parseXMLNode( element, xPath, linkData ):
        """Translate <externalReaction> element from xml."""

        xPath.append( '%s[@id="%s"]' % (element.tag, element.get('id') ) )
        exReac = externalReaction( **dict(element.items()) )
        exReac.ENDF_MFMT = map(int, exReac.ENDF_MFMT.split(','))
        xPath.pop()
        return exReac
