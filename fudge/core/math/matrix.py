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

from xData.ancestry import ancestry

matrixToken = 'matrix'
diagonalFormToken = 'diagonal'
symmetricFormToken = 'symmetric'
sparse_symmetricFormToken = 'sparse_symmetric'
asymmetricFormToken = 'asymmetric'
sparseFormToken = 'sparse_asymmetric'

class matrix( ancestry ):
    """
    Class for storing a matrix or two-dimensional array.
    This class supports diagonal, symmetric, asymmetric, and sparse matrices.
    Matrix data is stored as a list of lists, which is easily converted into a numpy array.
    """

    moniker = matrixToken

    def __init__(self, data, form=None, precision=None):
        """
        @data: list-of-lists containing matrix data
        @form: diagonal, symmetric, sparse, etc
        @precision: number of digits when printing. Necessary only if 'pretty' matrix output is desired.
        """
        ancestry.__init__( self )
        self.form = form
        self.data = data
        self.precision = precision

    @property
    def nrows(self): return len(self.data)

    @property
    def ncols(self): return len(self.data[0])
    
    def __getitem__(self, idx):
        return self.data[idx]

    def __add__(self, other):
        if self.form == other.form and self.precision == other.precision:
            return matrix( self.data + other.data, self.form, self.precision )
        raise Exception("Can't add together matrices with different form/precision")

    def check( self, info ): 
        """ 
        Run some simple checks on covariance matrices: 
            * look for negative eigenvals,
            * check ratio of smallest/largest eigenvals 
        """
        from fudge.gnd import warning
        warnings = []

        if self.form in (symmetricFormToken, diagonalFormToken, sparse_symmetricFormToken):
            import numpy
            A = numpy.matrix( self.data )
            # Check that the matrix is positive definite
            vals, vecs = numpy.linalg.eigh( A )
            if min(vals) < info['negativeEigenTolerance']:
                warnings.append( warning.negativeEigenvalues( len(vals[vals<0]), min(vals), self ))
            minpos, maxpos = min(vals[vals>=0]),max(vals[vals>=0])
            # Check that the condition number of the matrix is reasonable
            if minpos/maxpos < info['eigenvalueRatioTolerance'] and A.size != 1: 
                warnings.append( warning.badEigenvalueRatio( minpos/maxpos, self ) )
        return warnings

    def fix( self, **kw ):
        """
        Fix common eigenvalue problems: 
            * negative eigenvals,
            * bad ratio of smallest/largest eigenvals 
        """
        warnings = []
        if self.form in (symmetricFormToken,diagonalFormToken,sparse_symmetricFormToken) and ( kw['removeSmallEVs'] or kw['removeNegativeEVs'] ) :
            import numpy
            A = numpy.matrix( self.data )
            # Decompose A for later fixing
            e, O = numpy.linalg.eigh( A ) # stronger and more general than eigh
            v = [ O.T[i] for i in range( A.shape[0] ) ] # the eigenvectors are the columns of the orthogonal matrix O
            B = numpy.zeros_like( A )
            minval, maxval = min(e[e>=0]), max(e[e>=0]) # min and max eigenvalues
            ratio = minval/maxval
            evTol = max( kw['eigenvalueRatioTolerance'] * maxval, kw['eigenvalueAbsoluteTolerance'] )
            # Now construct B using the good eigenspaces of A
            for i in range( A.shape[0] ):
                if e[i] < 0.0 and ( abs( e[i] ) > max( evTol, abs( kw['negativeEigenTolerance'] ) ) ): #BAD BAD BAD    
                    warnings.append("WARNING: very bad bad bad eigenvalue = %e  for MF/MT=%s\n" % (e[i], kw['rowENDF_MFMT']))
                    if kw['removeSmallEVs'] and abs( e[i] ) < evTol: continue
                    if kw['removeNegativeEVs'] and e[i] < 0.0 : continue
                try:
                    B += numpy.outer( e[i]*v[i], v[i].T )
                except TypeError as err:
                    print B, e[i], v[i]
                    raise err
            self.data = B.tolist()
        return warnings
        
    def plot( self ):
        from numpy import mat
        from matplotlib.pyplot import matshow, show
        matshow( mat( self.data ) )
        show()


    def toXMLList( self, indent = '', **kwargs ) :

        if( self.precision ) :
            format = '%% -.%de' % self.precision
        else :
            format = kwargs.get( 'incrementalIndent', '%s' )

        xmlString = [indent+'<matrix rows="%s" columns="%s" form="%s"' 
                % (self.nrows, self.ncols, self.form)]
        if( self.precision ) : xmlString[0] += ' precision="%d"' % self.precision
        xmlString[0] += '>'
        
        # for some matrix forms we can save lots of space on xml output:
        if self.form == diagonalFormToken:
            for row in range(self.nrows):
                xmlString[-1] += format % self.data[row][row] + ' '
        elif self.form == symmetricFormToken:
            for row in range(self.nrows):
                nCols = row+1
                template = indent+'  '+' '.join([format]*nCols)
                xmlString.append( template % tuple(self.data[row][:nCols]) )
        elif self.form == asymmetricFormToken:
            for row in self.data:
                template = indent+'  '+' '.join([format]*len(row))
                xmlString.append( template % tuple(row) )
        elif self.form in (sparse_symmetricFormToken, sparseFormToken):
            # sparse matrices: give non-zero elements by listing
            #  row column length ...data...
            # For example, a diagonal 2x2 matrix would be:
            #
            # <matrix rows="2" columns="2" form="sparse_symmetric">
            #   0 0 1 0.234
            #   1 1 1 0.173
            # </matrix>

            # the buffer (buf) determines maximum distance between non-zero elements
            # before a new index must be given
            buf = 6
            rows,cols = self.nrows, self.ncols
            for row in range(rows):
                rowString = ''
                if self.form == sparse_symmetricFormToken: end = row+1
                else: end = self.ncols
                dat = self.data[row][:end]
                col, stop = 0, 0
                while col<end:
                    if dat[col]!=0:
                        stop = col+1
                        while stop < end:
                            if dat[stop]!=0: stop += 1
                            elif any(dat[stop:stop+buf]):
                                for i in range(buf):
                                    if stop+i<end and dat[stop+i]!=0: stop += i
                            else: break
                        template = ' '.join([format]*(stop-col))
                        rowString += '  %i %i %i ' % (row,col,stop-col) + template % tuple(dat[col:stop])
                        col = stop
                    col += 1
                if rowString:
                    xmlString.append(indent+rowString)
        else:
            raise TypeError("Don't know how to write matrix of form %s" % self.form)
        xmlString[-1] += '</matrix>'
        return xmlString

def parseXMLNode( mat, xPath, linkData ):

    xPath.append( mat.tag )
    import numpy
    if mat.text: matrixDat = map(float, mat.text.split())
    else: matrixDat = []
    nRows, nCols = int( mat.get('rows') ), int( mat.get('columns') )
    form = mat.get('form')

    if form==diagonalFormToken:
        if len(matrixDat) != nRows:
            raise TypeError("Wrong number of elements for diagonal matrix!")
        tmp = numpy.eye( nRows ) * numpy.array( matrixDat )
    elif form==symmetricFormToken:
        if len(matrixDat) != nRows * (nCols+1)/2:
            raise TypeError("Wrong number of elements for symmetric matrix!")
        start = 0
        tmp = numpy.zeros((nRows,nCols))
        for i in range(nRows):
            tmp[i,:i+1] = matrixDat[start:start+i+1]
            tmp[:i,i] = matrixDat[start:start+i]    # upper-diagonal portion
            start += i+1
    elif form==asymmetricFormToken:
        if len(matrixDat) != nRows * nCols:
            raise TypeError("Wrong number of elements in matrix!")
        tmp = numpy.array([matrixDat[j*nCols:(j+1)*nCols] for j in range(nRows)])
    elif form in (sparseFormToken, sparse_symmetricFormToken):
        tmp = numpy.zeros((nRows,nCols))
        idx = 0
        while idx<len(matrixDat):
            row, col, length = map(int, matrixDat[idx:idx+3])
            tmp[row, col:col+length] = matrixDat[idx+3: idx+3+length]
            idx += 3+length
        if form == sparse_symmetricFormToken:
            # symmetrize
            tmp = tmp + tmp.T - numpy.diag( tmp.diagonal() )
    else:
        raise Exception("Don't know how to read matrix of form %s!" % form)

    if 'precision' in mat.keys():
        precision=int(mat.get("precision"))
    else:
        precision=None

    matrix_ = matrix( tmp, form, precision=precision )
    xPath.pop()
    return matrix_
