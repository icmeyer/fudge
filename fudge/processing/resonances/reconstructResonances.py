#!/usr/bin/env python
#encoding: utf-8

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

"""
reconstruct resonance region
cmattoon, 12/1/2010

See ENDF-102 (endf documentation) appendix D for equations

Basic usage:
------------

    if x is a reactionSuite instance,::

        >>x.reconstructResonances(tolerance=0.01)

    This reconstructs all resolved/unresolved resonance sections. In each section,
    the results are accurate under linear interpolation to tolerance of 1% or better.
    Sections are summed together and then added to the appropriate background cross
    sections to form new pointwise, lin-lin cross sections that are stored in the
    appropriate reaction inside reactionSuite x.

Alternate uses:
---------------

    You can skip the final step (adding background cross sections) and just get the
    resonance parameter contribution to the cross section by doing::

        >>xsecs = reconstructResonances.reconstructResonances(x, tolerance=0.01)

    Here,::

        * xsecs = dictionary containing cross sections: {'total':XYs, 'elastic':XYs, ...}

    each cross section is an XYs class instance, containing data and also axes with units

    Another option would be to only reconstruct a single section::

        >> resCls = reconstructResonances.RMcrossSection(x)   # for Reich_Moore
        >> energy_grid = s.generateEnergyGrid()
        >> crossSections = s.getCrossSection( energy_grid )
        # the input to getCrossSection is the energy (or list of energies) in eV
        # crossSections are returned as a dictionary {'total':,'elastic':,'capture':,'fission':,}

        # improve grid to desired tolerance for linear interpolation:
        >> new_energy_grid, new_crossSections, messages = s.refineInterpolation(energy_grid, crossSections, tolerance=0.01)

"""
import numpy, collections, math
import abc
from fudge.gnd.reactionData import crossSection
from fudge.gnd.productData import distributions
import fudge.gnd.resonances
import fudge.processing.resonances.getCoulombWavefunctions as getCoulombWavefunctions

from xData import axes as axesModule
from xData import standards as standardsModule
from xData import XYs as XYsModule

__metaclass__ = type

debug = False   # recommend setting to True before debugging (disables multiprocessing)

VERBOSE = False

FISSIONCHANNEL, NEUTRONCHANNEL, CPCHANNEL, GAMMACHANNEL, COMPETATIVECHANNEL = range(5)

class ChannelDesignator:
    __slots__=[ 'l', 'J', 'reaction', 'index', 's', 'gfact', 'particleA', 'particleB', 'Xi', 'isElastic', 'channelClass', 'useRelativistic', 'eliminated' ]

    def __init__(self, l, J, reaction, index, s, gfact=None, particleA=None, particleB=None, Xi=0.0, isElastic=None, channelClass=None, useRelativistic=False, eliminated=False ):
        """
        Simple widget to specify a channel

        RRBaseClass.setResonanceParametersByChannel() creates these mostly and getAllowedTotalSpins() is used to determine the spins in there.
        So, if you're wondering why s is really 2*s, unlike l and J, check in those routines.

        :param l: orbital angular momentum of channel, an int
        :param J: total angular momentum of a channel, can be an int or 1/2 int (use the _eq_ below to avoid floating point comparisons)
        :param reaction: string, name of the reaction associated with this channel
        :param index: int, an optional index of the channel (useful if using this in an unordered dictionary)
        :param s: total spin of a channel, can be an int or 1/2 int (use the _eq_ below to avoid floating point comparisons)
        :param gfact: statistical factor
        :param particleA: the projectile, either a string ('n') or None if you don't need it
        :param particleB: the target, either a string ('Pu239') or None if you don't need it
        :param Xi: threshold energy in lab frame, in eV
        :param isElastic: flag to denote that this channel is, in fact, also incoming channel so this is an elastic channel
        :param channelClass: nature of channel: gamma, fission, neutron or charged particle
        :param useRelativistic: flag for using relativistic kinematics
        :param eliminated: flag for whether to eliminate this channel using Reich-Moore approximation (useful for gamma channels)
        :return:
        """
        self.l=l
        self.J=J
        self.reaction=reaction
        self.index=index
        self.s=s
        self.gfact=gfact
        self.particleA=particleA
        self.particleB=particleB
        self.Xi=Xi
        self.isElastic=isElastic
        self.channelClass=channelClass
        self.useRelativistic=useRelativistic
        self.eliminated=eliminated

    def __eq__(self, other):
        return self.l==other.l and int(2.0*self.J)==int(2.0*other.J) and self.reaction==other.reaction and \
            int(2.0*self.s)==int(2.0*other.s) and self.gfact==other.gfact and self.particleA==other.particleA and \
            self.particleB==other.particleB and self.isElastic==other.isElastic and self.channelClass==other.channelClass and \
            self.useRelativistic==other.useRelativistic and self.eliminated==other.eliminated

    def __hash__(self):
        theHash=0
        for s in ChannelDesignator.__slots__:
            if s == 'Xi':continue # is computable and is real, so lousy for hashing
            theHash+=eval("hash(self.%s)"%s)
        return theHash

    def __repr__(self):
        return "ChannelDesignator(l=%i, J=%s, reaction='%s', index=%i, s=%s, gfact=%s, particleA='%s', particleB='%s', Xi=%s, isElastic=%s, channelClass=%s, useRelativistic=%s, eliminated=%s)" \
               % (self.l, self.J, self.reaction, self.index, self.s, self.gfact, self.particleA, self.particleB, str(self.Xi), self.isElastic, self.channelClass, self.useRelativistic, self.eliminated)

    def has_same_J(self,other):
        return abs(self.J-other.J)<0.001

    def is_open(self,Ein): return Ein >= self.Xi


def spins_equal(s1,s2): return int(2.0*s1)==int(2.0*s2)


def getResonanceReconstructionClass( formalismMoniker ):
    try: return RRClassMap[formalismMoniker]['proc']
    except KeyError: raise TypeError, "Don't recognize resonance type %s" % formalismMoniker


def getAllowedTotalSpins( L, S, useFactor2Trick=True ):
    """
    Returns a list of allowed J values from summing angular momenta L and S, where
    :math:`\\vec{J}=\\vec{L}+\\vec{S}`
    which implies :math:`|L-S| \\leq J \\leq L+S`

    The useFactor2Trick flag tells the routine whether we are summing real angular momenta or momenta * 2.
    If the useFactor2Trick flag is true, then momenta are really momenta*2, meaning they can be pure integers,
    even if the real momenta refer to 1/2-integer values (e.g. spin).  The default is to useFactor2Trick because
    most C/C++/Fortran codes that compute angular momentum-stuff use the trick so they can use integer math.
    Also, it makes the use of the Python range() function possible.
    """
    if useFactor2Trick: return range( abs(L-S), L+S+2, 2 )
    else: return [ j/2.0 for j in getAllowedTotalSpins( int(L*2), int(S*2) ) ]


def reconstructResonances(reactionSuite, tolerance=None, verbose=False):
    """ reconstruct all resonance cross sections (resolved/unresolved) in reactionSuite,
    add results together for full (resonance region) pointwise cross section.
    If tolerance is specified, refine grid to required tolerance for (lin-lin) interpolation """

    egrids, xsecs = [], []

    if not reactionSuite.resonances.reconstructCrossSection:
        print ("      Resonance reconstruction was already done. Reconstruct again? y/N")
        if not raw_input().lower().startswith('y'): # bug!!!
            return xsecs

    # Helper function to reconstruct one region, used for single & multiple regions as well as URR ensembles
    def resolvedReconstruct( formalism, sectionIndex = None ):
        resCls = getResonanceReconstructionClass(formalism.moniker)
        reconstructClass = resCls( reactionSuite, sectionIndex, enableAngDists=False, verbose=verbose )
        egrid = reconstructClass.generateEnergyGrid()
        xsecs_now = reconstructClass.getCrossSection( egrid )
        if tolerance:
            egrid, xsecs_now, messages = reconstructClass.refineInterpolation(numpy.array(egrid), xsecs_now, tolerance)
            if verbose:
                for message in messages: print (message)
        return egrid, xsecs_now

    # Resolved resonance reconstruction
    if reactionSuite.resonances.resolved:
        # For multiple regions, we need to do each region separately, then add them to the unified xs table & egrid
        if reactionSuite.resonances.resolved.multipleRegions:
            if verbose:
                print( "      WARNING! Multiple resolved/unresolved energy regions are deprecated\n"
                        +"        and should be consolidated into single section")
            for RRidx in range(len(reactionSuite.resonances.resolved.regions)):
                formalism = reactionSuite.resonances.resolved.regions[RRidx].evaluated
                egrid_now, xsecs_now = resolvedReconstruct( formalism, RRidx )
                # merge with 'full' energy grid:
                egrids.append( egrid_now )
                xsecs.append( xsecs_now )
        # Single region, everything goes on unified grid
        else:
            formalism = reactionSuite.resonances.resolved.evaluated
            egrid_now, xsecs_now = resolvedReconstruct( formalism )
            # merge with 'full' energy grid:
            egrids.append( egrid_now )
            xsecs.append( xsecs_now )

    # Unresolved region has more complex logic, we may do one of a couple of things:
    #   a) do nothing
    #   b) reconstruct the average cross section assuming SLBW resonances (traditional ENDF)
    #   c) reconstruct the average xs and the PDF for the xs
    if reactionSuite.resonances.unresolved:
        formalism = reactionSuite.resonances.unresolved.evaluated
        reconstructClass = URRcrossSection( reactionSuite, verbose )
        if formalism.forSelfShieldingOnly: # don't reconstruct
            if verbose:
                print ("Skipping unresolved: for self shielding only")
        else:
            xsecs_now = reconstructClass.getCrossSection( )

            """
            if tolerance:
                # Disabling this section since ENDF manual now states that we should interpolate cross sections rather than parameters for URR.
                egrid, xsecs_now, messages = reconstructClass.refineInterpolation(numpy.array(egrid), xsecs_now, tolerance)
                if verbose:
                    for message in messages: print (message)
            """

            # meld with resolved region:
            egrids.append( None )
            xsecs.append( xsecs_now )

    # 'xsecs' list now holds one or more regions. Convert to pointwise or regions1d cross section instance:
    xsecs_final = {}
    if len(xsecs)==1:   # only one region: treat as XYs1d
        for key in xsecs[0]:
            if isinstance( xsecs[0][key], crossSection.XYs1d ): xsecs_final[key] = xsecs[0][key]
            else:
                axes_ = crossSection.defaultAxes()
                xsecs_final[key] = crossSection.XYs1d( axes=axes_, data=(egrids[0], xsecs[0][key]),
                        dataForm="XsAndYs", accuracy=(tolerance or 0.01) )
    else:               # multiple regions: treat as regions1d
        for key in xsecs[0]:
            pwxs = crossSection.regions1d( axes=crossSection.defaultAxes() )
            for idx in range(len(xsecs)):
                if isinstance( xsecs[idx][key], crossSection.XYs1d ): xys = xsecs[idx][key]
                else:
                    axes_ = crossSection.defaultAxes()
                    xys = crossSection.XYs1d( axes=axes_, data=(egrids[idx], xsecs[idx][key]),
                            dataForm="XsAndYs", accuracy=(tolerance or 0.01) )
                pwxs.append( xys )
            xsecs_final[key] = pwxs

    # note that this does not add XYs1d (ENDF-MF3) portion.
    # Use gnd.reactionSuite.reconstructResonances for that
    return xsecs_final


def reconstructAngularDistributions(reactionSuite, tolerance=None, verbose=False):
    """
    Reconstruct all pure two-body angular distributions from the resonance region.
    For MLBW and RM, that means 'elastic' channel only, but R-Matrix evaluations can support additional channels.
    SLBW cannot be used for angular distributions.

    Returns a Python dict.  They key is the reaction and the value is a reconstructed
    distributions.angular.XYs2d instance containing Legendre expansions for each incident energy.
    """
    angdists = {}
    angdistRegions = []
    egrids = []

    # Helper function to compute the per-region angular distributions
    def resolvedReconstruct( formalism, sectionIndex = None ):

        # Get the correct class
        resCls = getResonanceReconstructionClass(formalism.moniker)
        reconstructClass = resCls( reactionSuite, sectionIndex, enableAngDists=True, verbose=verbose )

        # Deal with potential thresholds by splitting up the energy grid at the thresholds
        fullEgrid = reconstructClass.generateEnergyGrid()
        if hasattr(reconstructClass,'_thresholds'):
            thresholdIndices = [0]
            for Xi in reconstructClass._thresholds:
                if Xi in fullEgrid:
                    thresholdIndices.append(list(fullEgrid).index(Xi))
                thresholdIndices.append(-1)
            subgrids = [fullEgrid[thresholdIndices[i]:thresholdIndices[i+1]] for i in range(len(thresholdIndices[:-1]))]
        else: subgrids=[fullEgrid]

        #for egrid in subgrids:
        #    print type(reconstructClass),"[%s, ..., %s]"%(str(egrid[0]),str(egrid[-1]))
        #exit()

        # Now do the calculation & merge the different regions
        angularResults={}
        for egrid in subgrids:
            print "Working egrid: [%s, ..., %s]"%(str(egrid[0]),str(egrid[-1]))
            thisAngularResults = reconstructClass.getAngularDistribution( egrid, keepL0Term=True, renormalize=True )
            if tolerance:
                raise NotImplementedError("Refining interpolation grid for angular distributions")
            for reaction, results in thisAngularResults.items():
                if reaction not in angularResults: angularResults[reaction] = []
                angularResults[reaction] += zip( egrid, numpy.array( results ).squeeze().T )
        return angularResults

    if reactionSuite.resonances.resolved:

        # Compute the per-region angular distributions & make a list of regional distributions
        if reactionSuite.resonances.resolved.multipleRegions:
            raise NotImplementedError("Angular reconstruction for multiple resolved regions, untested")
            if verbose:
                print( "      WARNING! Multiple resolved/unresolved energy regions are deprecated\n"
                        +"        and should be consolidated into single section")
            for RRidx in range(len(reactionSuite.resonances.resolved.regions)):
                formalism = reactionSuite.resonances.resolved.regions[RRidx].evaluated
                angdistRegions.append( resolvedReconstruct( formalism, RRidx ) )
        else:
            formalism = reactionSuite.resonances.resolved.evaluated
            angdistRegions.append( resolvedReconstruct( formalism ) )

        # Check that egrids don't overlap
        if len( angdistRegions ) ==1: pass
        else:
            for iRegion, this_region in enumerate(angdistRegions[:-1]):
                next_region = angdistRegions[iRegion+1]
                if this_region[-1][0] > next_region[0][0]:
                    raise ValueError( "this_region[-1][0] > next_region[0][0] for region %i" % iRegion )

        # 'angdistRegions' list holds one or more regions.  Convert to one Legendre coefficient table
        # right now only do elastic scattering (OK for MLBW & RM, but (unimplemented) RML can do more)
        angdists_final={}
        axes_ = distributions.angular.XYs2d.defaultAxes( asLegendre = True )
        if len(angdistRegions) == 1:    # only one region, treat as XYs2d
            for key in angdistRegions[0]:
                form = distributions.angular.XYs2d( axes = axes_ )
                for i1, E_Bs in enumerate( angdistRegions[0][key] ):
                    form.append( distributions.angular.pdfOfMu.Legendre(coefficients=E_Bs[1], value=E_Bs[0]))
                angdists_final[key] = form
        else:
            raise NotImplementedError("Still TBD")

    return angdists_final


def reconstructURRCrossSectionPDF(reactionSuite, tolerance=None, verbose=False, reconstructionScheme=None):

    # Determine how to represent the resonance region we are going to make up
    if reconstructionScheme is None:
        if reactionSuite.resonances.resolved.multipleRegions:
            reconstructionScheme = reactionSuite.resonances.resolved.regions[-1].evaluated.moniker
        else:
            reconstructionScheme = reactionSuite.resonances.resolved.evaluated.moniker
    if reconstructionScheme not in RRClassMap:
        raise ValueError("Unknown resonance moniker %s"%reconstructionScheme)

    # Set the resonance reconstruction class that will generate fake resonance regions for us
    resCls=getResonanceReconstructionClass(reconstructionScheme)

    return URRcrossSection( reactionSuite, verbose ).getURRPDF( resCls )


"""
@blockwise: function decorator for improving performance in resolved region.
Each 'getCrossSection' and 'getAngularDistribution' method is wrapped by this function.
If we have lots of incident energies, this splits up a calculation using the multiprocessing module.
May still need to tweak the 'NE' and 'nprocesses' variables for best performance.
"""
def blockwise(function):
    def wrapped(self,E,**kwargs):
        if debug:
            # disable multiprocessing
            if numpy.isscalar(E):
                E = numpy.array([[E]])
            else:
                E = numpy.array(E).reshape(len(E),1)
            return function(self,E,**kwargs)

        if numpy.isscalar(E):
            E = numpy.array([[E]])
            return function(self,E,**kwargs)
        else:
            NE = len(E)
            # turn E into a column vector
            E = numpy.array(E).reshape(NE,1)
            if NE < 1000: # faster to run directly
                return function(self,E,**kwargs)
            else:
                from multiprocessing import Process, Queue
                queue = Queue()

                def enqueue_result(elist, Slice, queue):
                    # perform the calculation, put result in the queue
                    result = function(self, elist, **kwargs)
                    queue.put( (Slice, result) )
                    return

                jobs = []
                nprocesses = 8  # number of processes to spawn
                # how many energies does each process calculate?
                chunk = int(numpy.ceil((NE+0.) / nprocesses))
                for pid in range(nprocesses): # start the calculations
                    Slice = slice(pid*chunk, (pid+1)*chunk)
                    p = Process(target=enqueue_result, args=(E[Slice], Slice, queue))
                    jobs.append(p)
                    p.start()

                for pid in range(nprocesses): # collect results as they finish
                    Slice, vals = queue.get()
                    if function.__name__ == 'getCrossSection':
                        if pid==0:
                            result = dict.fromkeys( vals )
                            for key in result: result[key] = numpy.zeros(NE)
                        for key in result:
                            result[key][Slice] = vals[key]
                    elif function.__name__ == 'getAngularDistribution':
                        if pid==0:
                            result = dict.fromkeys( vals )
                            for key in result: result[key] = [numpy.zeros((NE,1)) for L in range(len(vals[key]))]
                        for key in result:
                            for L in range(len(vals[key])):
                                result[key][L][Slice] = vals[key][L]
                    else:
                        raise NotImplementedError("Blockwise computation for function %s" % function.__name__)

                # allow child processes to exit:
                for job in jobs: job.join()
                return result
    return wrapped


# base class common to resolved and unresolved resonance reconstruction
class resonanceReconstructionBaseClass:

    __metaclass__ = abc.ABCMeta

    def __init__(self, reactionSuite, **kw):
        self.projectile = reactionSuite.projectile
        self.target = reactionSuite.target
        self.spin = self.target.getSpin().value
        neutronMass = reactionSuite.getParticle( 'n' ).getMass('amu')
        self.targetToNeutronMassRatio = self.target.getMass('amu') / neutronMass

    @abc.abstractmethod
    def getCrossSection(self, E): pass

    def k(self, energy):
        """
        For an incident neutron, with energy in eV, the ENDF manual states
        :math:`k = \frac{\sqrt{2m_n}}{\hbar}\frac{AWRI}{AWRI+1}\sqrt{|E|}`

        sqrt(2*neutronMass)/hbar == 2.196807e-3 (eV*barn)**-1/2. Thus for energy in eV, k is in b**-1/2
        """
        return (2.196807122623e-3 * self.targetToNeutronMassRatio /
                (self.targetToNeutronMassRatio+1) * numpy.sqrt(energy))

    """ refer to SAMMY manual page 9 for penetration/shift/phase factor equations: """
    def penetrationFactor(self, L, rho):
        if L==0: return rho
        elif L==1: return rho**3 / (1+rho**2)
        elif L==2: return rho**5 / (9+3*rho**2+rho**4)
        elif L==3: return rho**7 / (225+45*rho**2+6*rho**4+rho**6)
        elif L==4: return rho**9 / (11025+1575*rho**2+135*rho**4+10*rho**6+rho**8)
        elif L>4:
            # find it recursively
            P_Lminus1 = self.penetrationFactor(L-1,rho)
            S_Lminus1 = self.shiftFactor(L-1,rho)
            return rho**2 * P_Lminus1 / ((L-S_Lminus1)**2 + P_Lminus1**2)

    def shiftFactor(self, L, rho):
        """ calculate shift factor used in SLBW and MLBW formalisms """
        if L==0: return 0.0*rho   # rho may be an array
        elif L==1: return -1.0 / (1+rho**2)
        elif L==2: return -(18.0+3*rho**2) / (9+3*rho**2+rho**4)
        elif L==3: return -(675.0+90*rho**2+6*rho**4) / (225+45*rho**2+6*rho**4+rho**6)
        elif L==4: return -( (44100.0+4725*rho**2+270*rho**4+10*rho**6) /
                (11025+1575*rho**2+135*rho**4+10*rho**6+rho**8) )
        elif L>4:
            P_Lminus1 = self.penetrationFactor(L-1,rho)
            S_Lminus1 = self.shiftFactor(L-1,rho)
            return (rho**2 * (L-S_Lminus1) / ((L-S_Lminus1)**2+P_Lminus1**2) - L)

    def phi(self, L, rho):
        # calculate hard-sphere phase-shift
        if   L==0: return rho
        elif L==1: return rho-numpy.arctan(rho)
        elif L==2: return rho-numpy.arctan(3*rho/(3-rho**2))
        elif L==3: return rho-numpy.arctan(rho*(15-rho**2)/(15-6*rho**2))
        elif L==4: return rho-numpy.arctan(rho*(105-10*rho**2)/(105-45*rho**2+rho**4))
        elif L>4:
            P_Lminus1 = self.penetrationFactor(L-1,rho)
            S_Lminus1 = self.shiftFactor(L-1,rho)
            phi_Lminus1 = self.phi(L-1,rho)
            return phi_Lminus1 - numpy.arctan(P_Lminus1 / (L-S_Lminus1))

    # for use after the cross section has been calculated on the initial grid:
    def refineInterpolation(self, egrid, xsecs, tolerance=0.01):
        """ generateEnergyGrid may not give a fine enough grid to linearly interpolate to desired tolerance.
        My solution to that: for all consecutive points (x0,y0), (x1,y1) and (x2,y2) do a linear interpolation between
        (x0,y0) and (x2,y2). If the interpolation doesn't agree with (x1,y1) within tolerance,
        subdivide up the region by adding two more calculated points.  Keep iterating until interpolation agrees within tolerance.

        This means that in the end we will have more points than required for given tolerance.
        The results can be thinned (implemented in XYs)
        """
        def checkInterpolation(x,y):
            """
            Does a linear interpolation of each point from its two nearest neighbors,
            checks where the interpolation is insufficient and returns two lists:
                1: list of indices (in array x) where additional points are needed,
                2: list of corresponding energies where resonances need to be reconstructed and inserted into array y

            @type x: numpy.multiarray.ndarray
            @type y: numpy.multiarray.ndarray
            :return:
            """
            m = (y[2:]-y[:-2])/(x[2:]-x[:-2])
            delta_x = x[1:-1] - x[:-2]
            b = y[:-2]

            # add first and last points back in, for easier comparison with
            # original y values:
            interpolated = numpy.zeros_like(x)
            interpolated[1:-1] = m*delta_x+b
            interpolated[0] = y[0]; interpolated[-1] = y[-1]

            # find where original and interpolated grids differ by more than tolerance
            # silence div/0 warnings for this step, since xsc = 0 case is explicitly handled below
            with numpy.errstate( divide='ignore', invalid='ignore' ):
                delt = interpolated / y
                mask = (delt>1+tolerance) + (delt<1-tolerance) # boolean array

            badindices = numpy.arange(len(mask))[ mask ]
            # at these points, we need a finer mesh

            # switch to absolute convergence condition for very small cross sections (i.e. near thresholds):
            smallXSec = 1e-50
            zeros = (y[badindices-1]<smallXSec) + (y[badindices]<smallXSec) + (y[badindices+1]<smallXSec)
            if any(zeros):
                ignore = []
                for idx in badindices[ zeros ]:
                    if abs(y[idx]-y[idx-1])<1e-3 and abs(y[idx+1]-y[idx])<1e-3:
                        mask[ idx ] = False
                        ignore.append( idx )
                badindices = list(badindices)
                for idx in ignore[::-1]:
                    badindices.remove(idx)

            midpoints = (x[:-1]+x[1:])/2
            energies_needed = sorted( set( list( midpoints[mask[1:]]) + list( midpoints[mask[:-1]]) ) )
            return badindices, energies_needed

        def mergeArrays( newIdx, x1, x2, y1, y2 ):
            # from the list of 'bad' points in original array x1, obtain two new integer arrays, a1 and a2,
            # containing indices to insert x1 and x2 into merged array. Use these to quickly merge all data:
            newLen = len(x1)+len(x2)
            a1,a2 = [],[]
            nic = iter( newIdx )
            if len(newIdx)==1: idnow, idnext = nic.next(), -1
            else: idnow, idnext = nic.next(), nic.next()
            current, offset = idnow, 0
            extraPoint = False

            for val in xrange(newLen):
                if val==current:
                    a2.append(val)
                    offset += 1
                    if idnext==idnow+1:
                        current=idnext + offset
                        idnow = idnext
                        try: idnext = nic.next()
                        except StopIteration: idnext = -1
                    elif extraPoint:
                        extraPoint = False
                        current=idnext + offset
                        idnow = idnext
                        try: idnext = nic.next()
                        except StopIteration: idnext = -1
                    else:
                        extraPoint = True
                        current += 2
                else:
                    a1.append(val)

            # a1 and a2 now hold the indices for inserting x1 and x2 into merged array
            xnew = numpy.zeros(newLen)
            xnew[a1] = x1; xnew[a2] = x2
            ynew = {}
            for key in y1:
                ynew[key] = numpy.zeros(newLen)
                ynew[key][a1] = y1[key]; ynew[key][a2] = y2[key]
            return xnew, ynew

        messages = []
        reactionDone = dict.fromkeys(xsecs)  # values are None
        n_iter = 0
        addedPoints = 0
        while True:
            newX, newIdx = set(), set()
            for key in xsecs:
                if not any(xsecs[key]):
                    continue
                if not reactionDone[key]:
                    badindices, energies_needed = checkInterpolation(egrid,xsecs[key])
                    if len(energies_needed)==0: reactionDone[key] = True
                    newIdx.update( badindices )
                    newX.update( energies_needed )
            newX = sorted(newX)
            newIdx = sorted(newIdx)
            if len(newX)==0:    # success!
                break
            if n_iter > 20:
                messages.append("Iteration limit exceeded when refining interpolation grid!")
                break
            n_iter += 1
            addedPoints += len(newX)
            newY = self.getCrossSection( newX )
            # merge new x/y values with original list:
            egrid, xsecs = mergeArrays( newIdx, egrid, newX, xsecs, newY )

        messages.append("%i points were added (for total of %i) to achieve tolerance of %s%%" %
            (addedPoints, len(egrid), tolerance*100))
        return egrid, xsecs, messages


#### base class for resolved resonance reconstruction ####
class RRBaseClass(resonanceReconstructionBaseClass):

    __metaclass__ = abc.ABCMeta

    def __init__(self, reactionSuite, sectionIndex=None, lowerBound=None, upperBound=None, RR=None, **kw):
        super(RRBaseClass,self).__init__(reactionSuite, **kw)
        """ store resonance parameters in convenient structure for quick cross section calculations: """


        if sectionIndex is not None:
            # energy boundaries for this region (multiple regions are deprecated):
            energyRegion = reactionSuite.resonances.resolved.regions[sectionIndex]
        else:
            # only one energy region:
            energyRegion = reactionSuite.resonances.resolved

        if RR is None: self.RR = energyRegion.evaluated
        else: self.RR = RR

        if lowerBound is None: self.lowerBound = energyRegion.lowerBound.getValueAs('eV')
        else: self.lowerBound = lowerBound

        if upperBound is None: self.upperBound = energyRegion.upperBound.getValueAs('eV')
        else: self.upperBound = upperBound

    def sortLandJ(self):
        """
        SLBW, MLBW and Reich_Moore formalisms have similar structure
        it's convenient to sort their resonances by L and J
        This method should NOT be used for R-Matrix Limited
        """
        # make a unified table of resonance parameter data, convert to eV if necessary
        nRes = len( self.RR.resonanceParameters.table )
        params = ('energy','L','J','channelSpin','totalWidth','neutronWidth','captureWidth',
                'fissionWidthA','fissionWidthB')
        units = ('eV','','','','eV','eV','eV','eV','eV')
        data = [self.RR.resonanceParameters.table.getColumn( quant,unit ) for quant,unit in zip(params,units) ]
        for i in range(len(data)):
            if data[i] is None: data[i] = [0]*nRes
        table = numpy.array( data )

        # sort resonances by L and J, store parameters in numpy arrays
        self.Ls = []
        Llist = table[ params.index('L') ]
        for L in range(int(max( Llist ))+1):
            Lres = table[ :, table[ params.index('L') ]==L ]
            Jlist = Lres[ params.index('J') ]
            Js = []
            for J in sorted(set(Jlist)):
                LJres = Lres[ :, Lres[ params.index('J') ]==J ]
                spinList = LJres[ params.index('channelSpin') ]
                spins = []
                for spin in sorted(set(spinList)):
                    spinRes = LJres[ :, LJres[ params.index('channelSpin') ]==spin ]
                    energies = spinRes[ params.index('energy') ]
                    neutronWidth = ( spinRes[ params.index('neutronWidth') ] /
                        self.penetrationFactor(L,self.rho(abs(energies),L)) )
                    # FIXME for easier-to-read code, should I wait until getCrossSection
                    # to adjust the neutronWidth for penetrability at resonances?

                    spindict = {
                            'channelSpin': spin,
                            'energy': energies,
                            'neutronWidth': neutronWidth,
                            'captureWidth': spinRes[params.index('captureWidth')],
                            'fissionWidthA': spinRes[params.index('fissionWidthA')],
                            'fissionWidthB': spinRes[params.index('fissionWidthB')],
                            'shiftFactor': 0.5*self.shiftFactor(L,self.rho(numpy.abs(energies))),
                            }
                    spins.append( spindict )
                Jdict = {
                        'J': J,
                        'gfact': (2.0*abs(J)+1)/(2*(2*self.spin+1)),
                        'channelSpins': spins,
                        }
                Js.append( Jdict )

            Ldict = { 'L': L, 'Js': Js }
            self.Ls.append( Ldict )

        # for each L, gfactors should sum to 2*L+1.
        self.missingGfactor = {}
        for L in self.Ls:
            gsum = sum( [J['gfact'] * len(J['channelSpins']) for J in L['Js']] )
            self.missingGfactor[L['L']] = 2*L['L']+1 - gsum

        # for energy grid generation:
        self._energies = table[ params.index('energy') ]
        totalWidths = table[ params.index('totalWidth') ]
        if not any(totalWidths): # total widths aren't specified in Reich_Moore case
            totalWidths = ( table[params.index('neutronWidth')] + table[params.index('captureWidth')]
                    + table[params.index('fissionWidthA')] + table[params.index('fissionWidthB')] )
        self._widths = totalWidths

    def rho(self, E, L=None):
        """get the channel radius, rho. If L is specified try to get L-dependent value"""
        if self.RR.calculateChannelRadius:
            a = 0.123 * self.target.getMass('amu')**(1./3.) + 0.08  # eq. D.14 in ENDF manual, a in b^-1/2
        else:
            if self.RR.scatteringRadius.isEnergyDependent():
                a = self.RR.scatteringRadius.getValueAs('10**-12*cm', energyGrid=E[:,0])   # a in b^-1/2
            else:
                a = self.RR.scatteringRadius.getValueAs( '10**-12*cm', L=L )   # a in b^-1/2
        return self.k(E) * a # dimensionless

    def generateEnergyGrid(self):
        """ Create an initial energy grid by merging a rough mesh for the entire region (~10 points / decade)
        with a denser grid around each resonance. For the denser grid, multiply the total resonance width by
        the 'resonancePos' array defined below. """
        energies, widths = self._energies, self._widths
        thresholds = []
        if hasattr(self, '_thresholds'):
            thresholds = self._thresholds
        lowBound, highBound = self.lowerBound, self.upperBound
        # ignore negative resonances
        for lidx in range(len(energies)):
            if energies[lidx] > 0: break
        energies = energies[lidx:]
        widths = widths[lidx:]
        # generate grid for a single peak, should be good to 1% using linear interpolation:
        resonancePos = numpy.array([
            0.000e+00, 1.000e-03, 2.000e-03, 3.000e-03, 4.000e-03, 5.000e-03, 6.000e-03, 7.000e-03, 8.000e-03, 9.000e-03, 1.000e-02, 2.000e-02,
            3.000e-02, 4.000e-02, 5.000e-02, 6.000e-02, 7.000e-02, 8.000e-02, 9.000e-02, 1.000e-01, 1.100e-01, 1.200e-01, 1.300e-01, 1.400e-01,
            1.500e-01, 1.600e-01, 1.700e-01, 1.800e-01, 1.900e-01, 2.000e-01, 2.100e-01, 2.200e-01, 2.300e-01, 2.400e-01, 2.500e-01, 2.600e-01,
            2.800e-01, 3.000e-01, 3.200e-01, 3.400e-01, 3.600e-01, 3.800e-01, 4.000e-01, 4.200e-01, 4.400e-01, 4.600e-01, 4.800e-01, 5.000e-01,
            5.500e-01, 6.000e-01, 6.500e-01, 7.000e-01, 7.500e-01, 8.000e-01, 8.500e-01, 9.000e-01, 9.500e-01, 1.000e+00, 1.050e+00, 1.100e+00,
            1.150e+00, 1.200e+00, 1.250e+00, 1.300e+00, 1.350e+00, 1.400e+00, 1.450e+00, 1.500e+00, 1.550e+00, 1.600e+00, 1.650e+00, 1.700e+00,
            1.750e+00, 1.800e+00, 1.850e+00, 1.900e+00, 1.950e+00, 2.000e+00, 2.050e+00, 2.100e+00, 2.150e+00, 2.200e+00, 2.250e+00, 2.300e+00,
            2.350e+00, 2.400e+00, 2.450e+00, 2.500e+00, 2.600e+00, 2.700e+00, 2.800e+00, 2.900e+00, 3.000e+00, 3.100e+00, 3.200e+00, 3.300e+00,
            3.400e+00, 3.600e+00, 3.800e+00, 4.000e+00, 4.200e+00, 4.400e+00, 4.600e+00, 4.800e+00, 5.000e+00, 5.200e+00, 5.400e+00, 5.600e+00,
            5.800e+00, 6.000e+00, 6.200e+00, 6.400e+00, 6.500e+00, 6.800e+00, 7.000e+00, 7.500e+00, 8.000e+00, 8.500e+00, 9.000e+00, 9.500e+00,
            1.000e+01, 1.050e+01, 1.100e+01, 1.150e+01, 1.200e+01, 1.250e+01, 1.300e+01, 1.350e+01, 1.400e+01, 1.450e+01, 1.500e+01, 1.550e+01,
            1.600e+01, 1.700e+01, 1.800e+01, 1.900e+01, 2.000e+01, 2.100e+01, 2.200e+01, 2.300e+01, 2.400e+01, 2.500e+01, 2.600e+01, 2.700e+01,
            2.800e+01, 2.900e+01, 3.000e+01, 3.100e+01, 3.200e+01, 3.300e+01, 3.400e+01, 3.600e+01, 3.800e+01, 4.000e+01, 4.200e+01, 4.400e+01,
            4.600e+01, 4.800e+01, 5.000e+01, 5.300e+01, 5.600e+01, 5.900e+01, 6.200e+01, 6.600e+01, 7.000e+01, 7.400e+01, 7.800e+01, 8.200e+01,
            8.600e+01, 9.000e+01, 9.400e+01, 9.800e+01, 1.020e+02, 1.060e+02, 1.098e+02, 1.140e+02, 1.180e+02, 1.232e+02, 1.260e+02, 1.300e+02,
            1.382e+02, 1.550e+02, 1.600e+02, 1.739e+02, 1.800e+02, 1.951e+02, 2.000e+02, 2.100e+02, 2.189e+02, 2.300e+02, 2.456e+02, 2.500e+02,
            2.600e+02, 2.756e+02, 3.092e+02, 3.200e+02, 3.469e+02, 3.600e+02, 3.892e+02, 4.000e+02, 4.200e+02, 4.367e+02, 4.600e+02, 4.800e+02,
            5.000e+02, 6.000e+02, 7.000e+02, 8.000e+02, 9.000e+02, 1.000e+03 ])

        grid = []
        # get the midpoints (on log10 scale) between each resonance:
        # emid = [lowBound] + list(10**( ( numpy.log10(energies[1:])+numpy.log10(energies[:-1]) ) / 2.0)) + [highBound]
        # or get midpoints on linear scale:
        emid = [lowBound] + [(e1+e2)/2.0 for e1,e2 in zip(energies[1:],energies[:-1])] + [highBound]
        for e,w,lowedge,highedge in zip(energies,widths,emid[:-1],emid[1:]):
            points = e-w*resonancePos
            grid += [lowedge] + list(points[points>lowedge])
            points = e+w*resonancePos[1:]
            grid += list(points[points<highedge])
        # also add rough grid, to cover any big gaps between resonances, should give at least 10 points per decade:
        npoints = numpy.ceil( numpy.log10(highBound)-numpy.log10(lowBound) ) * 10
        grid += list( numpy.logspace(numpy.log10(lowBound),numpy.log10(highBound), npoints) )[1:-1]
        grid += [lowBound, highBound, 0.0253]   # region boundaries + thermal
        # if threshold reactions present, add dense grid at and above threshold
        for threshold in thresholds:
            grid += [threshold]
            grid += list( threshold + resonancePos * 1e-2 )
        grid = sorted(set(grid))
        # toss any points outside of energy bounds:
        grid = grid[ grid.index(lowBound) : grid.index(highBound)+1 ]
        return grid

    def setResonanceParametersByChannel( self, multipleSScheme='NJOY', useReichMooreApproximation=False, Ein=None ):
        """
        Reorganize member data into channels (relies heavily on groundwork in sortLandJ).
        """
        self.nResonances = len( self.RR.resonanceParameters.table )
        self.lMax = self.RR.LvaluesNeededForConvergence
        self.channelConstantsBc = []
        allowedSs = getAllowedTotalSpins( 0.5, self.spin, useFactor2Trick=False )

        # Make a unified table of resonance parameter data, convert to eV if necessary
        lList = []
        params = ('energy','L','J','channelSpin','totalWidth','neutronWidth','captureWidth', 'fissionWidthA','fissionWidthB')
        units = ('eV','','','','eV','eV','eV','eV','eV')
        data = [ self.RR.resonanceParameters.table.getColumn( quant,unit ) for quant,unit in zip(params,units) ]
        for i in range(len(data)):
            if data[i] is None: data[i] = [0]*self.nResonances

        def addOrUpdateDict( theDict, theKey, theValue ):
            if not theKey in theDict: theDict[ theKey ] = {}
            theDict[ theKey ][ theValue[0] ] = theValue[1]

        # Now make the dictionary of channels
        channelDict = collections.OrderedDict()
        for iR in range( self.nResonances ):
            ER = data[0][iR]
            L =  data[1][iR]
            J =  data[2][iR]
            S =  None # not given in MLBW, RM or RML, I just list it here for completeness
            GT = data[4][iR]
            GN = data[5][iR]
            GG = data[6][iR]
            GF = data[7][iR]
            GX = data[8][iR]
            JisAllowed = False
            self.lMax = max( self.lMax, L )
            if L not in lList: lList.append(L)
            allowedSByThisJl = []
            for SS in allowedSs:
                if J in getAllowedTotalSpins( L, SS, useFactor2Trick=False ):
                    JisAllowed = True
                    allowedSByThisJl.append( SS )
            if not JisAllowed: raise ValueError( "Invalid total angular momentum and/or orbital momentum: cannot couple up to J = "+str(J)+" with I = "+str(self.spin)+", i = 0.5 and L = "+str(L) )
            gfact = (2.0*abs(J)+1)/(2*(2*self.spin+1))
            numAllowedSByThisJl = len( allowedSByThisJl )

            # Way recommended by NJOY:
            #   * One of valid S's get width, other(s) get zero width
            #   * Zero width channels left in sum to get potential scattering correct
            #   * Gets good (cs from U) to (cs from Fudge) comparison; good (cs from U) to (cs from BB)
            if multipleSScheme == 'NJOY':
                addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'elastic', 0, allowedSByThisJl[0], gfact, None, None, 0.0, True, NEUTRONCHANNEL, False, False ), ( iR, GN ) )
                addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'capture', 0, allowedSByThisJl[0], gfact, None, None, 0.0, False, GAMMACHANNEL, False, useReichMooreApproximation ), ( iR, GG ) )
                if GF != 0.0: addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'fission', 0, allowedSByThisJl[0], gfact, None, None, 0.0, False, FISSIONCHANNEL, False, False ), ( iR, GF ) )
                if GX != 0.0: addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'competitive', 0, allowedSByThisJl[0], gfact, None, None, 0.0, False, COMPETATIVECHANNEL, False, False ), ( iR, GX ) )
                for SS in allowedSByThisJl[1:]:
                    addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'elastic', 0, SS, gfact, None, None, 0.0, True, NEUTRONCHANNEL, False, False ), ( iR, 0.0 ) )
                    addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'capture', 0, SS, gfact, None, None, 0.0, False, GAMMACHANNEL, False, useReichMooreApproximation ), ( iR, 0.0 ) )
                    if GF != 0.0: addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'fission', 0, SS, gfact, None, None, 0.0, False, FISSIONCHANNEL, False, False ), ( iR, 0.0 ) )
                    if GX != 0.0: addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'competitive', 0, SS, gfact, None, None, 0.0, False, COMPETATIVECHANNEL, False, False ), ( iR, 0.0 ) )

            # Way hinted at by ENDF manual:
            #   * Width divided equally between channels with valid S's
            #   * All channels left in sum to get potential scattering correct
            #   * Gets poor (cs from U) to (cs from Fudge) comparison; poor (cs from U) to (cs from BB)
            elif multipleSScheme == 'ENDF':
                for SS in allowedSByThisJl:
                    addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'elastic', 0, SS, gfact, None, None, 0.0, True, NEUTRONCHANNEL, False, False ), ( iR, GN/numAllowedSByThisJl ) )
                    addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'capture', 0, SS, gfact, None, None, 0.0, False, GAMMACHANNEL, False, useReichMooreApproximation ), ( iR, GG/numAllowedSByThisJl ) )
                    if GF != 0.0: addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'fission', 0, SS, gfact, None, None, 0.0, False, FISSIONCHANNEL, False, False ), ( iR, GF/numAllowedSByThisJl ) )
                    if GX != 0.0: addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'competitive', 0, SS, gfact, None, None, 0.0, False, COMPETATIVECHANNEL, False, False ), ( iR, GX/numAllowedSByThisJl ) )

            # Ignore problem:
            #   * Ignore spin of channels and the fact may be multiple valid spins
            #   * Gets best (cs from U) to (cs from Fudge) comparison; poor (cs from U) to (cs from BB)
            else :
                addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'elastic', 0, S, gfact, None, None, 0.0, True, NEUTRONCHANNEL, False, False ), ( iR, GN ) )
                addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'capture', 0, S, gfact, None, None, 0.0, False, GAMMACHANNEL, False, useReichMooreApproximation ), ( iR, GG ) )
                if GF != 0.0: addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'fission', 0, S, gfact, None, None, 0.0, False, FISSIONCHANNEL, False, False ), ( iR, GF ) )
                if GX != 0.0: addOrUpdateDict( channelDict, ChannelDesignator( L, J, 'competitive', 0, S, gfact, None, None, 0.0, False, COMPETATIVECHANNEL, False, False ), ( iR, GX ) )

        # Take care of extra l's needed to get potential scattering correct
        # Make a single elastic channel with a zero width resonance at the energy of the first real resonance
        # This won't add to the resonance scattering part, but it will make a potential scattering part.
        # We add in channels for all spins and total angular momenta to make sure get the angular momentum algebra correct.
        for l in range( 0, self.lMax+1 ):
            for s in allowedSs:
                for j in getAllowedTotalSpins( l, s, useFactor2Trick=False ):
                    newChannel = ChannelDesignator( l, j, 'elastic', 0, s, (2.0*abs(j)+1)/(2*(2*self.spin+1)), None, None, 0.0, True, NEUTRONCHANNEL, False, False )
                    if not newChannel in channelDict: addOrUpdateDict( channelDict, newChannel, ( 0, 0 ) )

        # Set up the channel->resonance mappings
        self.allChannels = channelDict
        self.channels = collections.OrderedDict()  # just the kept ones
        self.eliminatedChannels = collections.OrderedDict()
        for c in self.allChannels:
            if c.eliminated:    self.eliminatedChannels[ c ] = self.allChannels[ c ]
            else:               self.channels[ c ] = self.allChannels[ c ]
        self.nChannels = len( self.channels )
        self.identityMatrix = numpy.identity( self.nChannels, dtype=complex )

    def resetResonanceParametersByChannel(self, multipleSScheme='NJOY', useReichMooreApproximation=False, Ein=None ): pass

    def getChannelConstantsBc( self ):
        raise NotImplementedError( "Override in derived classes if used" )

    def getRMatrix( self, Ein ): raise NotImplementedError( "Override in derived classes if used" )

    def getKMatrix( self, Ein ): raise NotImplementedError( "Override in derived classes if used" )

    def getAMatrix( self, Ein ): raise NotImplementedError( "Override in derived classes if used" )

    def getL0Matrix( self, Ein ):
        """
        Get the L0 matrix of Froehner:

            ..math::
                {\bf L^0}_{cc'} = \delta_{cc'} (L_c-B_c)

        where

            ..math::
                L_c = S_c + i P_c

        """
        if self.channelConstantsBc == []: self.channelConstantsBc = self.getChannelConstantsBc()
        L0 = numpy.zeros( (len(Ein), self.nChannels, self.nChannels), dtype=complex )
        for ic,c in enumerate(self.channels):
            rho = self.rho( Ein-c.Xi, c.l )
            shift = self.shiftFactor( c.l, rho ).flatten()
            penet = self.penetrationFactor( c.l, rho ).flatten()

            # Note, you have to add the numpy.array's this way to make a complex number
            # because the numpy array trickery doesn't work with the complex() or
            # numpy.complex() constructors
            L0[:,ic,ic] = shift + 1j* penet - self.channelConstantsBc[ ic ]
        return L0

    def getXMatrix( self, Ein ):
        """
        Get the X matrix for use in computing W.  X is:

            ..math::
                {\bf X}_{cc'} = P^{-1/2}_c ( ( {\bf I} - {\bf R}{\bf L^0} )^{-1}{\bf R} )_{cc'} P_{c'}^{-1/2}\delta_{JJ'}
        """
        L0 = self.getL0Matrix( Ein )
        penFact = numpy.ones( ( len(Ein), self.nChannels ), dtype=float )
        X = numpy.zeros( ( len(Ein), self.nChannels, self.nChannels ), dtype=complex )

        # Precompute phase factor, sqrt(Penetrability)
        for ic, c in enumerate( self.channels ):
            if c.channelClass in [NEUTRONCHANNEL, CPCHANNEL]: penFact[:,ic] = numpy.sqrt( L0[:,ic,ic].imag )

        # Compute the (unscaled) X matrix
        # Hafta be real careful about combining numpy's broadcasting rules with numpy's linear algebra
        R = self.getRMatrix( Ein )
        for iE in range(len(Ein)):
            thisR = numpy.mat(R[iE])
            thisL0 = numpy.mat(L0[iE])
            X[iE] = numpy.linalg.inv( numpy.mat(self.identityMatrix) - thisR * thisL0 ) * thisR

        # Apply the sqrt(Penetrability) rescaling
        for ic1, c1 in enumerate( self.channels ):
            for ic2, c2 in enumerate( self.channels ):
                if c1.J != c2.J: continue
                X[:, ic1, ic2] *= penFact[:, ic1] * penFact[:, ic2]

        return X

    def getWMatrix( self, Ein ):
        """
        Get the W matrix for use in computing U.  W is:

            ..math::
                {\bf W} = {\bf I} + 2i{\bf X}
        """
        W = numpy.zeros( ( len(Ein), self.nChannels, self.nChannels ), dtype=complex )
        W[ :, numpy.identity( self.nChannels, dtype=bool ) ] = 1
        W += 2.0j * self.getXMatrix( Ein )
        return W

    def getEiPhis( self, Ein, useTabulatedScatteringRadius=True, enableExtraCoulombPhase=False ):
        """
        The phase factor for the collision matrix:

            ..math::
                \Omega_c = e^{-\varphi_c}
        """

        # Precompute phase factor
        eiphis = []
        for ic, c in enumerate( self.channels ):
            if c.reaction == 'elastic':
                # For calculating phi, default is to use tabulated scattering radius:
                if useTabulatedScatteringRadius:
                    if self.RR.scatteringRadius.isEnergyDependent():
                        rhohat = self.RR.scatteringRadius.getValueAs('10*fm', Ein-c.Xi) * self.k(Ein-c.Xi)
                    else:
                        rhohat = self.RR.scatteringRadius.getValueAs('10*fm', L=c.l) * self.k(Ein-c.Xi)
                else: rhohat = self.rho(Ein-c.Xi, L=c.l)
                phi = self.phi( c.l, rhohat )
                eiphis.append( numpy.exp( -1j * phi ) )
            else:
                eiphis.append( numpy.ones( Ein.shape, dtype=complex ) )
        return eiphis

    def getScatteringMatrixU( self, Ein, useTabulatedScatteringRadius=True, enableExtraCoulombPhase=False ):
        """
        Compute the scattering matrix using
        """
        # Make sure all channels are open at all requested energies
        if not numpy.all([c.is_open(Ein) for c in self.channels]): raise ValueError("One or more channels are not open on all energies in requested energy grid")

        # Initialize lists and matrices
        eiphis =  self.getEiPhis( Ein,
                                  useTabulatedScatteringRadius=useTabulatedScatteringRadius,
                                  enableExtraCoulombPhase=enableExtraCoulombPhase )
        W = self.getWMatrix( Ein )

        # This adds in the phase factors to get us U
        U = numpy.zeros( ( len(Ein), self.nChannels, self.nChannels ), dtype=complex )
        for ic1 in range( self.nChannels ):
            for ic2 in range( self.nChannels ):
                U[:, ic1, ic2 ] = W[:, ic1, ic2 ] * (eiphis[ic1][:] * eiphis[ic2][:]).flatten()
        return U

    def getScatteringMatrixT( self, Ein, useTabulatedScatteringRadius=True, enableExtraCoulombPhase=False ):
        # Make sure all channels are open at all requested energies
        if not numpy.all([c.is_open(Ein) for c in self.channels]): raise ValueError("One or more channels are not open on all energies in requested energy grid")

        T = numpy.zeros( ( len(Ein), self.nChannels, self.nChannels ), dtype=complex )
        U = self.getScatteringMatrixU( Ein,
                                       useTabulatedScatteringRadius=useTabulatedScatteringRadius,
                                       enableExtraCoulombPhase=enableExtraCoulombPhase )
        for ic1 in range( self.nChannels ):
            for ic2 in range( self.nChannels ):
                T[:, ic1, ic2 ] = (ic1==ic2) - U[:, ic1, ic2 ]
        return T

    def getLMax(self,maxLmax=10):
        """
        LMax is determined by the behavior of the Blatt-Biedenharn Zbar coefficients.  Inside each one, there is
        a Racah coefficient and a Clebsh-Gordon coefficient.  The CG coefficient looks like this:
                ( l1 l2  L )
                (  0  0  0 )
        So, this means two things.  First, the CG coeff (and hence Zbar) will be zero if l1+l2+L=odd.
        Second, the maximum value of L will be l1max+l2max.  Hence, Lmax=2*lmax.
        """
        return min( max( [ 2*xL['L'] for xL in self.Ls ] ), maxLmax )

    def getParticleSpins(self,rxn):
        if rxn=='elastic': # easy peasy lemon-squeezy
            spinA = 0.5                                          # Assuming that we have a neutron as a projectile, projSpin is 1/2
            spinB = self.spin                                    # Target spin from baseclass
        elif ' + ' in rxn:
            spinA = None
            spinB = None
            pa,pb=rxn.split(' + ')
            if pa=='gamma': pa='photon'
            if pb=='gamma': pb='photon'
            for p in self.RR.getRootAncestor().particles:
                if pa==str(p): spinA=float(p.getSpin())
                if pb==str(p): spinB=float(p.getSpin())
                if ('_e' in pa or '_e' in pb) and hasattr(p,'levels'):
                    for lev in p.levels:
                        if type(lev)==str: continue
                        levName = '%s_e%i'%(p,lev)
                        if pa==levName: spinA=float(p.levels[lev].getSpin())
                        if pb==levName: spinB=float(p.levels[lev].getSpin())
        elif "competitive" in rxn:
            spinA = 0.5 # ficticious, but it doesn't matter anyway
            spinB = self.spin
        else: raise ValueError('Cannot determine spins for reactants in reaction "%s"'%rxn)
        return spinA, spinB

    @blockwise
    def getAngularDistribution(self, E, keepL0Term=True, renormalize=True, outChannelNames=None,
                               useTabulatedScatteringRadius=True, enableExtraCoulombPhase=False ):
        """

        :param numpy.array(type=float) E:
        :param bool keepL0Term:
        :param bool renormalize:
        :param str reactionp:
        :param bool useTabulatedScatteringRadius:
        :param bool enableExtraCoulombPhase:
        :return:
        :rtype: dict
        """
        from numericalFunctions import angularMomentumCoupling as nf_amc

        # Make sure the incident energies are in the correct form for vectorization
        if type(E) in [float, numpy.float64]: E = numpy.array(E).reshape(1,1)
        else: E = numpy.array(E).reshape(len(E),1)

        # Make sure all channels are open at all requested energies
        self.resetResonanceParametersByChannel( Ein=E )
        if not numpy.all([c.is_open(E) for c in self.channels]): raise ValueError("One or more channels are not open on all energies in requested energy grid")

        # Get the names of the input channel and all output channels to consider
        channelNames = set([c.reaction for c in self.channels])
        inChannelName = '%s + %s' % (self.projectile, self.target)
        if inChannelName not in channelNames:   # FIXME change MLBW and R-M to label channels by particle pairs like LRF=7
            if 'elastic' in channelNames:
                inChannelName = 'elastic'
        if outChannelNames is None:
            outChannelNames = set([chan.reaction for chan in self.channels if not chan.eliminated and chan.reaction not in ['capture','fission','fissionA','fissionB','competitive']])

        # Set up variables, first the easy ones
        k = self.k(E)                                           # Relative momentum, comes out in b^-1/2
        B = {key:[] for key in outChannelNames}                 # List of Blatt-Biedenharn coefficients, used in Legendre series expansion of the angular distribution
        results = {key:[] for key in outChannelNames}
        relTol = 1e-8                                           # Relative tolerance used to decide when to cut off Legendre series
        Lmax = self.getLMax( )                                  # Lmax also used to decide when to cut off Legendre series

        # Now, the T matrix, the most important variable of all...
        T = self.getScatteringMatrixT( E,                       # The scattering matrix
                                       useTabulatedScatteringRadius=useTabulatedScatteringRadius,
                                       enableExtraCoulombPhase=enableExtraCoulombPhase )

        # The in channel stuff...
        projSpin, targSpin = self.getParticleSpins(inChannelName)
        prefactor = 1.0/k/k/(2*projSpin+1)/(2*targSpin+1)       # Prefactor for cross section, gets units, main energy dependence, and spin dep. prefactor
        allowedSpins = getAllowedTotalSpins( targSpin,          # Possible values of the total channel spin, based on the projectile spin (projSpin) and target spin (targSpin)
                                             projSpin,
                                             False )
        incidentChannels = [(i,chan) for i,chan in enumerate(self.channels)
                            if not chan.eliminated and chan.reaction == inChannelName]

        # Loop over out channels
        for reactionp in outChannelNames:
            ejectSpin, resSpin = self.getParticleSpins(reactionp)
            allowedSpinsp = getAllowedTotalSpins( resSpin,          # Possible values of the total channel spin, based on the ejectile spin (ejectSpin) and residual nucleus spin (resSpin)
                                                  ejectSpin,
                                                  False )
            outgoingChannels = [(i,chan) for i,chan in enumerate(self.channels)
                                if not chan.eliminated and chan.reaction == reactionp]

            # Main algorithm
            # Some words on the looping over L here.  There are 3 reasons to keep looping:
            #   1. We have less than 3 Legendre moments (L=0,1,2).  At threshold we have L=0 only, but otherwise had better have more.
            #   2. If we hit LMax or all the biggest L moments are too small, then stop, otherwise keep going
            #   3. We end on an odd L index.  That means Lmax must be even because LMax = last L-1
            # By the way, we must have an even LMax.  See the getLMax() documentation for reasoning.
            L = 0
            while len(B[reactionp])<=3 or ( numpy.any( numpy.abs(B[reactionp][-1])>=relTol*B[reactionp][0] ) and L<=Lmax ) or L%2==0:
                B[reactionp].append(numpy.zeros_like(E))
                for S in allowedSpins:
                    for Sp in allowedSpinsp:
                        spinFactor =  pow( -1, S - Sp ) / 4.0
                        for i1, c1 in incidentChannels:
                            if c1.s is not None and not spins_equal(c1.s, S): continue # c1.s != S: continue
                            for i2, c2 in incidentChannels:
                                if c2.s is not None and not spins_equal(c2.s, S): continue # c2.s != S: continue
                                Z = nf_amc.zbar_coefficient( int(2.*c1.l), int(2.*c1.J), int(2.*c2.l), int(2.*c2.J), int(2.*S), int(2.*L) )
                                if Z == 0.0: continue
                                for i1p, c1p in outgoingChannels:
                                    if c1.J != c1p.J: continue
                                    if c1p.s is not None and not spins_equal(c1p.s, Sp): continue # c1p.s != Sp: continue
                                    for i2p, c2p in outgoingChannels:
                                        if c2.J != c2p.J: continue
                                        if c2p.s is not None and not spins_equal(c2p.s, Sp): continue # c2p.s != Sp: continue
                                        Zp = nf_amc.zbar_coefficient( int(2*c1p.l), int(2*c1p.J), int(2*c2p.l), int(2*c2p.J), int(2*Sp), int(2*L) )
                                        if Zp == 0.0: continue
                                        thisB = spinFactor * Z * Zp * ( T[:,i1,i1p].conj() * T[:,i2,i2p] ).real
                                        B[reactionp][-1] += thisB[:,numpy.newaxis]
                L += 1

            for l,coefs in enumerate( B[reactionp] ):
                results[reactionp].append( prefactor / ( 2.0*l+1.0 ) * coefs )
            if renormalize:
                L0term=results[reactionp][0]
                if any(L0term<1e-16): L0term[L0term<1e-16]=1e-16 #takes care of questionable behavior near threshold
                results[reactionp] = [ x/L0term for x in results[reactionp] ]

        return results

    def getBackgroundRMatrix(self, Ein, Emin, Emax, gamWidth, pole_strength, Rinf=None):
        """
        Froehner's background R matrix.  This could be vectorized for speed.  Not sure if it would be useful though.
        """
        Rbackground = numpy.zeros( len(Ein), dtype=complex )
        I = (Emax-Emin)
        Eave = 0.5*(Emax+Emin)
        for iEE,EE in enumerate(Ein):
            if EE < Emin: raise ValueError("Ein="+str(EE)+" is below Emin="+str(Emin))
            if EE > Emax: raise ValueError("Ein="+str(EE)+" is above Emax="+str(Emax))
            dE=EE-Eave
            A = 2.0*dE/I
            B = (I*I/4.0-dE*dE)
            if B == 0.0:
                Rbackground[iEE] = 0.0j
                continue
            if Rinf is not None:
                Rbackground[iEE] = \
                    2.0*pole_strength*complex(numpy.arctanh(A), gamWidth*I/4.0/B)+Rinf
            else:
                Rbackground[iEE] = \
                    2.0*pole_strength*complex(numpy.arctanh(A), gamWidth*I/4.0/B)
        return Rbackground

    def getAverageQuantities(self,resonancesPerBin=10,computeUncertainty=False):
        """
        Computes average widths and level spacings from the set of resonance parameters in self, on a per-channel basis

        The averages are computed in equal lethargy bins starting at the lowest resonance energy in a sequence up to the
        upperBound of the resonance region.  I tried to keep on average 10 resonances/logrithmic bin so I can get a
        reasonable average.

        :param resonancesPerBin: the number of resonances per logrithmic bin to aim for, on average
        :param computeUncertainty: toggle the calculation of the uncertainty of the quantities
        :return: a dictionary of results, sorted by channel
        """
        from numpy import mean,var
        import pqu.PQU
        results={}
        for c in self.channels:
            bins = list(numpy.logspace(
                math.log10(max(self.lowerBound,self._energies[self.channels[c].keys()[0]])),
                math.log10(self.upperBound),
                max(len(self.channels[c])//resonancesPerBin,1)+1 ))
            results[c]={'energyGrid':bins,'widths':[0.0 for x in bins[0:-1]],'spacings':[0.0 for xx in bins[0:-1]]}
            # compute averages in a bin
            for i1 in range(len(bins)-1):
                lastER=None
                spacingsList=[]
                widthList=[]
                ERList=[self._energies[iR] for iR in self.channels[c]]
                ERList.sort()
                for ER in ERList:
                    if ER>=bins[i1] and ER<=bins[i1+1]:
                        widthList.append(self.channels[c][iR])
                        if lastER is not None and lastER>self.lowerBound and ER>self.lowerBound:
                            spacingsList.append(ER-lastER)
                        lastER=ER
                if len(spacingsList)>1:
                    if computeUncertainty:
                        results[c]['spacings'][i1]=pqu.PQU.PQU(value=mean(spacingsList),uncertainty=math.sqrt(var(spacingsList)),unit='eV')
                        results[c]['widths'][i1]=pqu.PQU.PQU(value=mean(widthList),uncertainty=math.sqrt(var(widthList)),unit='eV')
                    else:
                        results[c]['spacings'][i1]=pqu.PQU.PQU(value=mean(spacingsList),unit='eV')
                        results[c]['widths'][i1]=pqu.PQU.PQU(value=mean(widthList),unit='eV')
                elif len(widthList)==1:
                    results[c]['spacings'][i1]=pqu.PQU.PQU(value=-1e9,unit='eV')
                    results[c]['widths'][i1]=pqu.PQU.PQU(value=widthList[0],unit='eV')
                else:
                    results[c]['spacings'][i1]=pqu.PQU.PQU(value=-1e9,unit='eV')
                    results[c]['widths'][i1]=pqu.PQU.PQU(value=0.0,unit='eV')
        return results

    def getTransmissionCoefficientsFromSumRule(self,computeUncertainty=False):
        """
        Use Moldauer's sum rule to extract the transmission coefficients directly from the RRR tables
            P.A. Moldauer Phys. Rev. Lett. 19, 1047-1048 (1967)

        :param computeUncertainty: toggle the calculation of the uncertainty of the transmission coefficients
        :return: a dictionary of results, sorted by channel
        """
        import pqu.PQU
        aves=self.getAverageQuantities(computeUncertainty=computeUncertainty)
        results={}
        for c in aves:
            results[c]={'Tc':[],'energyGrid':aves[c]['energyGrid']}
            for i in range(len(aves[c]['energyGrid'])-1):
                twoPiGOverD=2.0*math.pi*aves[c]['widths'][i]/aves[c]['spacings'][i]
                if twoPiGOverD < 1e-16: results[c]['Tc'].append(pqu.PQU.PQU(value=0.0,unit=''))
                else: results[c]['Tc'].append(0.5*twoPiGOverD*twoPiGOverD*( math.sqrt(1.0+4.0/twoPiGOverD/twoPiGOverD) - 1.0))
        return results

    def getPoleStrength(self,computeUncertainty=False):
        """
        Computes the neutron pole strength from the transmission coefficients

        ..math::
            s_c(E) = \rho_c(E)\overline{\Gamma_c}/2P_c = T_c(E)/4\pi P_c

        :param computeUncertainty:
        :return:
        """
        results = {}
        Tcs = self.getTransmissionCoefficientsFromSumRule(computeUncertainty)
        results.update(Tcs)
        for c in Tcs:
            results[c]['sc']=[]
            for i in range(len(Tcs[c]['energyGrid'])-1):
                rho=self.rho(Tcs[c]['energyGrid'][i],c.l)
                results[c]['sc'].append( (results[c]['Tc'][i])/(4.0*math.pi*self.penetrationFactor(c.l,rho)) )
        return results

    def getStrengthFunction(self,computeUncertainty=False):
        results={}
        sc = self.getPoleStrength(computeUncertainty=computeUncertainty)
        for c in sc:
            if sc[c]['sc'][0]>0.0 or len(sc[c]['sc'])==1: results[c]=sc[c]['sc'][0]
            else: results[c]=sc[c]['sc'][1]
        return results

    def getScatteringLength(self):
        '''
        Compute R' in b**1/2, should be close to AP

        The potential scattering cross section sigPot = 4 Pi (R')^2, so we compute the potential scattering cross section at E=1e-5 eV
        :return:
        '''
        E=[1e-5]
        sigPotL = []
        for c in self.channels:
            if not c.isElastic: continue
            sigPotL.append( ( ( 2.0 * c.l + 1 ) ) * 4.0 * numpy.pi * ( numpy.sin( self.phi( c.l, self.rho(E,c.l) ) ) )**2 / self.k(E)**2 )
        sigPot = sum(sigPotL)
        return numpy.sqrt(sigPot/4.0/numpy.pi)

    def getPorterThomasFitToWidths(self, Emin=0.0, Emax=None, verbose=False):
        '''
        Perform a channel-by-channel fit of the histogram of widths to a Porter-Thomas distribution.

        :param verbose:
        :return:
        '''
        try: import scipy.optimize
        except ImportError:
            print "WARNING: scipy.optimize not imported, Porter-Thomas analysis not done"
            return {}
        try: import numpy
        except ImportError:
            print "WARNING: numpy's histogram() and mean() functions not imported, Porter-Thomas analysis not done"
            return {}
        results={}

        for c in self.channels:
            if verbose: print
            if verbose: print c
            if c.eliminated:
                if verbose: print '    eliminated'
                results[c]={'dof':0.0,'ddof':0.0}
            elif len(self.channels[c])<2:
                if verbose: print '    not enough data'
                results[c]={'dof':1.0,'ddof':0.0}
            else:
                widthList=[]
                for iR in self.channels[c]:
                    ER=self._energies[iR]
                    if Emin is not None and ER < Emin: continue
                    if Emax is not None and ER > Emax: continue
                    widthList.append(self.channels[c][iR])
                    aveWidth = numpy.mean(widthList)
                norm=len(widthList)
                if verbose: print '    widths', widthList
                if all([w==widthList[0] for w in widthList]):
                    if verbose: print '    widths identical'
                    results[c]={'dof':1.0,'ddof':0.0}
                else:
                    if verbose: print '    scaled widths', [w/aveWidth for w in widthList]
                    hist, bin_edges=numpy.histogram([w/aveWidth for w in widthList])
                    if verbose: print '    hist',hist
                    if verbose: print '    bins', bin_edges
                    if verbose: print '    fitting:'

                    def PorterThomasDistribution(y, nu):
                        """
                        Porter-Thomas distribution
                        Froehner's eq. (277).
                        Really just a chi^2 distribution with nu degrees of freedom

                        :param y:
                        :param nu:
                        :return:
                        """
                        if verbose: print '        y',y
                        if verbose: print '        norm',norm
                        if verbose: print '        nu',nu
                        gam = math.gamma(nu/2.0)
                        if nu < 2.0:
                            ycut=pow(1e4*gam,-1.0/(1.0-nu/2.0))
                            y[y < ycut]=ycut
                        return norm*numpy.exp(-y)*pow(y,nu/2.0-1.0)/gam

                    if False:
                        from xData import XYs
                        xys=[[],[]]
                        for i in range(len(hist)):
                            xys[0].append((bin_edges[i]+bin_edges[i+1])/2)
                            xys[1].append(hist[i])
                        XYs.XYs( data=xys, dataForm='xsandys' ).plot()

                    popt,pcov = scipy.optimize.curve_fit( PorterThomasDistribution, [(bin_edges[i]+bin_edges[i+1])/2 for i in range(len(bin_edges)-1)], hist, bounds=[0.0,numpy.inf] )
                    if verbose: print '    popt',popt
                    if verbose: print '    pcov',pcov
                    results[c]={'dof':popt[0],'ddof':math.sqrt(pcov[0,0])}
        return results


#### Single-level Breit-Wigner ###
class SLBWcrossSection(RRBaseClass):
    """
    given a resonance region in SLBW format,
    create a class with all data required to reconstruct

    Note, the resonances in the SLBW format each correspond to different "levels" and so do not
    interfere.  This is unlike all of the other RRR formats.  So, while one resonance energy
    and one width go with one channel and all the channels associated with one resonance energy
    go together to make one reaction, the reactions for each resonance are added incoherently (no
    interference effects at all).
    """

    def __init__(self, reactionSuite, sectionIndex=None, enableAngDists=False, verbose=True, **kw):
        super(SLBWcrossSection, self).__init__(reactionSuite, sectionIndex, **kw)
        self.verbose = verbose
        self.sortLandJ()
        if self.verbose:
            print ("From %f to %f eV, reconstructing using Single-level Breit-Wigner" %
                    (self.lowerBound,self.upperBound))
        if enableAngDists: self.setResonanceParametersByChannel()

    def setResonanceParametersByChannel( self, multipleSScheme='NJOY', useReichMooreApproximation=False, Ein=None ):
        """
        Reorganize member data into channels (relies heavily on groundwork in sortLandJ).

        Note, unlike the getResonanceParametersByChannel() function in MLBW, RM or RML,
        the fact that different resonances are entirely different reactions means that the
        channelDicts have to have an additional layer of sorting that corresponds to the SLBW "level".
        """
        # make a unified table of resonance parameter data, convert to eV if necessary
        self.nResonances = len( self.RR.resonanceParameters.table )
        params = ('energy','L','J','channelSpin','totalWidth','neutronWidth','captureWidth',
                'fissionWidthA','fissionWidthB')
        units = ('eV','','','','eV','eV','eV','eV','eV')
        data = [self.RR.resonanceParameters.table.getColumn( quant,unit ) for quant,unit in zip(params,units) ]
        for i in range(len(data)):
            if data[i] is None: data[i] = [0]*self.nResonances

        allowedSs = getAllowedTotalSpins( 0.5, self.spin, useFactor2Trick=False )

        # Now make the dictionary of channels, grouped by independent level
        channelDicts = []
        for iR in range( self.nResonances ):
            ER = data[0][iR]
            L =  data[1][iR]
            J =  data[2][iR]
            S =  None # not given in SLBW, I just list it here for completeness
            GT = data[4][iR]
            GN = data[5][iR]
            GG = data[6][iR]
            GF = data[7][iR]
            GX = data[8][iR]
            JisAllowed = False
            allowedSByThisJl = []
            for SS in allowedSs:
                if J in getAllowedTotalSpins( L, SS, useFactor2Trick=False ):
                    JisAllowed = True
                    allowedSByThisJl.append( SS )
            if not JisAllowed: raise ValueError( "Invalid total angular momentum and/or orbital momentum: cannot couple up to J = "+str(J)+" with I = "+str(self.spin)+", i = 0.5 and L = "+str(L) )
            gfact = (2.0*abs(J)+1)/(2*(2*self.spin+1))
            channelDict=collections.OrderedDict()
            numAllowedSByThisJl = len( allowedSByThisJl )

            # Way recommended by NJOY:
            #   * One of valid S's get width, other(s) get zero width
            #   * Zero width channels left in sum to get potential scattering correct
            #   * Gets good (cs from U) to (cs from Fudge) comparison; good (cs from U) to (cs from BB)
            if multipleSScheme == 'NJOY':
                channelDict[ ChannelDesignator( L, J, 'elastic', iR, allowedSByThisJl[0], gfact, None, None, 0.0, True, NEUTRONCHANNEL, False, False )] = [ ( ER, GN ) ]
                channelDict[ ChannelDesignator( L, J, 'capture', iR, allowedSByThisJl[0], gfact, None, None, 0.0, False, GAMMACHANNEL, False, False )] = [ ( ER, GG ) ]
                if GF != 0.0: channelDict[ ChannelDesignator( L, J, 'fission', iR, allowedSByThisJl[0], gfact, None, None, 0.0, False, FISSIONCHANNEL, False, False )]     = [ ( ER, GF ) ]
                if GX != 0.0: channelDict[ ChannelDesignator( L, J, 'competitive', iR, allowedSByThisJl[0], gfact, None, None, 0.0, False, COMPETATIVECHANNEL, False, False )] = [ ( ER, GX ) ]
                for SS in allowedSByThisJl[1:]:
                    channelDict[ ChannelDesignator( L, J, 'elastic', iR, SS, gfact, None, None, 0.0, True, NEUTRONCHANNEL, False, False )] = [ ( ER, 0.0 ) ]
                    channelDict[ ChannelDesignator( L, J, 'capture', iR, SS, gfact, None, None, 0.0, False, GAMMACHANNEL, False, False )] = [ ( ER, 0.0 ) ]
                    if GF != 0.0: channelDict[ ChannelDesignator( L, J, 'fission', iR, SS, gfact, None, None, 0.0, False, FISSIONCHANNEL, False, False )]     = [ ( ER, 0.0 ) ]
                    if GX != 0.0: channelDict[ ChannelDesignator( L, J, 'competitive', iR, SS, gfact, None, None, 0.0, False, COMPETATIVECHANNEL, False, False )] = [ ( ER, 0.0 ) ]

            # Way hinted at by ENDF manual:
            #   * Width divided equally between channels with valid S's
            #   * All channels left in sum to get potential scattering correct
            #   * Gets poor (cs from U) to (cs from Fudge) comparison; poor (cs from U) to (cs from BB)
            elif multipleSScheme == 'ENDF':
                for SS in allowedSByThisJl:
                    channelDict[ ChannelDesignator( L, J, 'elastic', iR, SS, gfact, None, None, 0.0, True, NEUTRONCHANNEL, False, False )] = [ ( ER, GN/numAllowedSByThisJl ) ]
                    channelDict[ ChannelDesignator( L, J, 'capture', iR, SS, gfact, None, None, 0.0, False, GAMMACHANNEL, False, False )] = [ ( ER, GG/numAllowedSByThisJl ) ]
                    if GF != 0.0: channelDict[ ChannelDesignator( L, J, 'fission', iR, SS, gfact, None, None, 0.0, False, FISSIONCHANNEL, False, False )]     = [ ( ER, GF/numAllowedSByThisJl ) ]
                    if GX != 0.0: channelDict[ ChannelDesignator( L, J, 'competitive', iR, SS, gfact, None, None, 0.0, False, COMPETATIVECHANNEL, False, False )] = [ ( ER, GX/numAllowedSByThisJl ) ]

            # Ignore problem:
            #   * Ignore spin of channels and the fact may be multiple valid spins
            #   * Gets best (cs from U) to (cs from Fudge) comparison; poor (cs from U) to (cs from BB)
            else :
                channelDict[ ChannelDesignator( L, J, 'elastic', iR, S, gfact, None, None, 0.0, True, NEUTRONCHANNEL, False, False )] = [ ( ER, GN ) ]
                channelDict[ ChannelDesignator( L, J, 'capture', iR, S, gfact, None, None, 0.0, False, GAMMACHANNEL, False, False )] = [ ( ER, GG ) ]
                if GF != 0.0: channelDict[ ChannelDesignator( L, J, 'fission', iR, S, gfact, None, None, 0.0, False, FISSIONCHANNEL, False, False )]     = [ ( ER, GF ) ]
                if GX != 0.0: channelDict[ ChannelDesignator( L, J, 'competitive', iR, S, gfact, None, None, 0.0, False, COMPETATIVECHANNEL, False, False )] = [ ( ER, GX ) ]
            channelDicts.append( channelDict )

        self.channels = channelDicts

    def getScatteringMatrixU( self, Ein, useTabulatedScatteringRadius=True, enableExtraCoulombPhase=False ):
        """
        Compute the scattering matrix

        Note, unlike the getScatteringMatrixU() function in other resonance classes,
        the fact that different resonances are entirely different reactions means that the
        channelDicts have to have an additional layer of sorting that corresponds to the SLBW "level".
        """
        U = collections.OrderedDict(
            [ ( iL, numpy.diag(len(cs)*[complex(1.0)]) ) for iL,cs in enumerate(self.channels) ] )
        rho = self.rho(Ein)

        # For calculating phi, default is to use tabulated scattering radius:
        if useTabulatedScatteringRadius:
            if self.RR.scatteringRadius.isEnergyDependent():
                rhohat = self.RR.scatteringRadius.getValueAs('10*fm', Ein) * self.k(Ein)
            else:
                rhohat = self.RR.scatteringRadius.getValueAs('10*fm') * self.k(Ein)
        else: rhohat = self.rho(Ein)

        for iL,channels in enumerate(self.channels):
            ER = self._energies[iL]
            ERp = ER
            GamTot = 0.0
            eiphis = [ ]
            sqrtgams = [ ] # all are real
            for c in channels:
                if c.reaction == 'elastic':
                    Gam = ( channels[c][0][1] *
                        self.penetrationFactor( c.l, self.rho( Ein,       c.l ) ) /
                        self.penetrationFactor( c.l, self.rho( abs( ER ), c.l ) ) )
                    ERp += (
                            self.shiftFactor( c.l, self.rho( abs( ER ), c.l ) ) -
                            self.shiftFactor( c.l, self.rho( Ein,       c.l ) )
                        ) * channels[c][0][1] / (2.0 * self.penetrationFactor( c.l, self.rho( abs(ER), c.l) ) )
                    eiphis.append( numpy.exp( complex( 0.0, -self.phi( c.l, rhohat ) ) ) )
                else:
                    Gam = channels[c][0][1]
                    eiphis.append( complex( 1.0, 0.0 ) )
                sqrtgams.append( numpy.sqrt( Gam ) )
                GamTot += Gam
            for i1, c1 in enumerate(channels):
                denominator = complex( ERp - Ein, -GamTot/2.0 ) # c1 & c2 have same l
                for i2, c2 in enumerate(channels):
                    if c2.index != c1.index: continue
                    U[iL][i1][i2] += complex( 0.0, sqrtgams[i1]*sqrtgams[i2] ) / denominator
                    U[iL][i1][i2] *= eiphis[i1] * eiphis[i2]
        return U

    def getAngularDistribution(self, E, **kwargs ):

        raise NotImplementedError("Angular distributions cannot be safely reconstructed using Single-Level Breit-Wigner approximation")

    @blockwise
    def getCrossSection(self, E):
        captureSum = 0
        elasticSum = 0
        fissionSum = 0
        rho = self.rho(E)
        # for calculating phi, always use tabulated scattering radius:
        rhohat = self.RR.scatteringRadius.getValueAs('10*fm') * self.k(E)
        for L in self.Ls:
            l = L['L']
            phi = self.phi(l,rhohat)
            P = self.penetrationFactor(l,rho)
            S = 0.5*self.shiftFactor(l,rho)
            for J in L['Js']:
                gfactor = J['gfact']
                for spin in J['channelSpins']:
                    dE = (E-(spin['energy']+spin['neutronWidth']*(spin['shiftFactor']-S)))
                    totalWidth = P*spin['neutronWidth'] + spin['captureWidth'] + spin['fissionWidthA']
                    denominator = dE**2 + totalWidth**2 / 4
                    captureSum += gfactor * numpy.sum( ( P * spin['neutronWidth'] * spin['captureWidth'] ) / denominator , axis=1)
                    fissionSum += gfactor * numpy.sum( ( P * spin['neutronWidth'] * spin['fissionWidthA'] ) / denominator , axis=1)
                    elasticSum += gfactor * numpy.sum( ( P*spin['neutronWidth'] * ( P*spin['neutronWidth']
                        - 2 * numpy.sin(phi)**2 * totalWidth + 4 * numpy.sin(phi)*numpy.cos(phi) * (E-spin['energy']) ) )
                        / denominator , axis=1)
            # numpy.sum(..., axis=1) returns row vector, so also convert first term to row vector:
            elasticSum += 4*(2*l+1)*numpy.sin(phi)[:,0]**2

        # get common factor 'beta' as a row vector:
        beta = numpy.pi / self.k(E)[:,0]**2
        capture = beta * captureSum
        elastic = beta * elasticSum
        fission = beta * fissionSum
        for reaction in (capture,elastic,fission):
            reaction[ reaction<=0 ] = 0
        total = elastic + capture + fission
        nonelastic = capture + fission
        result = {'total':total, 'elastic':elastic, 'capture':capture, 'fission':fission, 'nonelastic':nonelastic}
        return result


#### Multi-level Breit-Wigner ###
class MLBWcrossSection(RRBaseClass):
    """
    Given a resonance region in MLBW format,
    create a class with all data required to reconstruct

    Only the elastic channel differs from SLBW
    """

    def __init__(self, reactionSuite, sectionIndex=None, enableAngDists=False, verbose=True, **kw):
        super(MLBWcrossSection, self).__init__(reactionSuite, sectionIndex, **kw)
        self.verbose = verbose
        self.sortLandJ()
        if self.verbose:
            print ("From %f to %f eV, reconstructing using Multi-level Breit-Wigner" %
                    (self.lowerBound,self.upperBound))
        if enableAngDists: self.setResonanceParametersByChannel()

    def getChannelConstantsBc( self ):
        """
        For ENDF's MLBW, should be :math:`B_c = S_\\ell(|E_\\lambda|)`
        where :math:`\\ell` is the channel angular momentum and :math:`\\lambda` is the resonances index for the channel
        """
        raise NotImplementedError( "write me" )

    def getScatteringMatrixU( self, Ein, useTabulatedScatteringRadius=True, enableExtraCoulombPhase=False ):
        """
        Compute the scattering matrix.  We could have used the generic U function in the base class,
        but Froehner has "simplifications" that we took advantage of here (that and I don't know what the
        R matrix is exactly in the case of MLBW).
        """
        # Initialize lists and matrices
        sqrtGam = numpy.zeros( ( len(Ein), self.nChannels, self.nResonances ) )
        U = numpy.zeros( ( len(Ein), self.nChannels, self.nChannels ), dtype=complex )
        U[ :, numpy.identity( self.nChannels, dtype=bool ) ] = 1
        Gtots = self.nResonances * [ 0.0 ]
        ERp = list( self._energies )
        eiphis = self.getEiPhis(  Ein, useTabulatedScatteringRadius = useTabulatedScatteringRadius )

        # Precompute sqrt(Gamma) and sum up to get the total Gamma
        # Total Gamma may be different from what is given in the ENDF data file
        # Also, work out energy shifts
        for ic, c in enumerate( self.channels ):
            if c.reaction == 'elastic':
                for iR, G in self.channels[c].items():
                    ER = self._energies[iR]
                    Gam = ( G *
                        self.penetrationFactor( c.l, self.rho( Ein,       c.l ) ) /
                        self.penetrationFactor( c.l, self.rho( abs( ER ), c.l ) ) )
                    ERp[iR] += (
                            self.shiftFactor( c.l, self.rho( abs( ER ), c.l ) ) -
                            self.shiftFactor( c.l, self.rho( Ein,       c.l ) )
                        ) * G / 2.0 / self.penetrationFactor( c.l, self.rho( abs(ER), c.l) )
                    sqrtGam[ :, ic, iR ] = numpy.sqrt(Gam).T
                    Gtots[ iR ] += Gam
            else:
                for iR, G in self.channels[c].items():
                    ER = self._energies[iR]
                    sqrtGam[ :, ic, iR ] = numpy.sqrt(G).T
                    Gtots[ iR ] += G

        # If the width in the ENDF file is bigger than the sum of parts, there is a competitive width
        # otherwise, the ENDF value is wrong, use the one we get from the sum of parts
        for iR in range( self.nResonances ):
            mask = Gtots[ iR ] < self._widths[ iR ]
            Gtots[ iR ][ mask ] = self._widths[ iR ]

        # Compute the denominator
        DEN = ERp - Ein - 1j*numpy.array(Gtots)/2.0

        # Compute U itself.  Can we accelerate this with numpy routines?
        for i1 in range( self.nChannels ):
            for i2 in range( i1, self.nChannels ):
                U[:,i1,i2] += 1j * numpy.sum( sqrtGam[:,i1,:] * sqrtGam[:,i2,:] / DEN[:,:,0].T, axis=1 )
                U[:,i1,i2] *= (eiphis[i1] * eiphis[i2]).flatten()
                U[:,i2,i1] = U[:,i1,i2]
        return U

    @blockwise
    def getCrossSection(self, E):
        captureSum = 0
        elasticSum = 0
        fissionSum = 0
        rho = self.rho(E)
        # for phi:
        if self.RR.scatteringRadius.isEnergyDependent():
            rhohat = numpy.array(self.RR.scatteringRadius.getValueAs('10*fm', E[:,0]))[:,numpy.newaxis] * self.k(E)
        else:
            rhohat = self.RR.scatteringRadius.getValueAs('10*fm') * self.k(E)
        for L in self.Ls:
            l = L['L']
            phi = self.phi(l,rhohat)
            P = self.penetrationFactor(l,rho)
            S = 0.5*self.shiftFactor(l,rho)
            for J in L['Js']:
                gfactor = J['gfact']
                for spin in J['channelSpins']:
                    dE = (E-(spin['energy']+spin['neutronWidth']*(spin['shiftFactor']-S)))
                    totalWidth = P*spin['neutronWidth'] + spin['captureWidth'] + spin['fissionWidthA']
                    denominator = dE**2 + totalWidth**2 / 4
                    commonFactor = P * spin['neutronWidth'] / denominator
                    captureSum += gfactor * numpy.sum( commonFactor * spin['captureWidth'] , axis=1)
                    fissionSum += gfactor * numpy.sum( commonFactor * spin['fissionWidthA'] , axis=1)

                    # simple elastic method, Eq D.19 - D.21 in ENDF 102. This has numerical issues, however:
                    # U_nn = numpy.exp(-2*1j*phi[:,0]) * (1 + numpy.sum( 1j*P*spin['neutronWidth'] /
                    #     (spin['energy']-E-1j*totalWidth/2) , axis=1))
                    # elasticSum += gfactor * abs( (1-U_nn)**2 )

                    # Instead of the above, use the following from RECENT:
                    elasticTerm1 = numpy.sum( totalWidth/2 * commonFactor, axis=1 )
                    elasticTerm2 = numpy.sum( dE * commonFactor, axis=1 )
                    sin2ps = 2*numpy.sin(phi[:,0])*numpy.cos(phi[:,0])
                    sinps2 = 2*numpy.sin(phi[:,0])**2
                    elasticSum += gfactor * ((sinps2-elasticTerm1)**2 + (sin2ps+elasticTerm2)**2)
            if True: #addMissingGfactor:
                elasticSum += 2*numpy.sin(phi[:,0])**2 * 2*self.missingGfactor[l]

        # get common factor 'beta' as a row vector:
        beta = numpy.pi / self.k(E)[:,0]**2
        capture = beta * captureSum
        elastic = beta * elasticSum
        fission = beta * fissionSum
        for reaction in (capture,elastic,fission):
            reaction[ reaction<=0 ] = 0
        total = elastic + capture + fission
        nonelastic = capture + fission
        return {'total':total, 'elastic':elastic, 'capture':capture, 'fission':fission, 'nonelastic':nonelastic}


###### Reich_Moore and R-Matrix Limited ######

# some helper functions:

def getR_S(E, Eres, captureWidth, widths, penetrabilities):
    """
    Both versions of Reich_Moore formalisms (LRF=3 and 7) rely on building the complex matrix 'R'.
    Here we break it up into the real component R and the imaginary component S,
    which represent symmetric and anti-symmetric scattering respectively

    matrix elements R[i,j] and S[i,j] =

    (summed over resonances) partialWidth[i]*partialWidth[j] * coefficient/(dE**2+captureWidth**2),

    for the ith/jth open channel. For S, the coefficient is 'dE', for R 'captureWidth'
    and partialWidth[i] = widths[i] * penetrabilities[i]

        ( widths[i] is a row vector of resonance widths, and penetrabilities[i] is a column vector
        of the penetrability for each incident energy )

    After computing R and S, invert using invertMatrices to find RI and SI such that (I+R+jS)*(I+RI+jSI) = I
    where I is the identity matrix, and j = sqrt(-1)

    Incident energy dependence appears in both in E and the penetrabilities

    Additional documentation from RECENT::

      THE CROSS SECTIONS ARE DEFINED TO BE,

      TOTAL        =2*GJ*REAL(I - U(N,N))
      ABSORPTION   =4*GJ*(REAL(RHO(N,N)) - RHO(N,N)**2)
                   =  GJ*(I - U(N,N)**2)
      ELASTIC      =  GJ*(I - U(N,N))**2
      FISSION      =4*GJ*(SUM OVER C)(RHO(N,C)**2)
      CAPTURE      = ABSORPTION - FISSION

      WHICH ARE COMPLETELY DEFINED IN TERMS OF U(N,N) AND RHO(N,C),

      RHO(N,C)     =I - INVERSE(I - K)
      U(N,N)       =EXP(-I*2*PS)*(2*INVERSE(I - K) - I)
                   =(COS(2*PS) - I*SIN(2*PS))*(2*INVERSE(I - K) - I)
                   =(COS(2*PS) - I*SIN(2*PS))*(1 - 2*RHO(N,N))

                   =COS(2*PS)*(I-2*REAL(RHO)) - I*2*SIN(2*PS)*IM(RHO)

      ... (cmattoon: cutting some of the documentation here) ...

      (I - K)      = (R + I) - I*S

      R            = SQRT(GAM(C)/2*GAM(C*)/2)*(GAM/2)/DEN
      S            = SQRT(GAM(C)/2*GAM(C*)/2)*(ER-E)/DEN
      GAM(R)       = ELIMINATED RADIATIVE WIDTH
      GAM(C)       = PARTIAL WIDE FOR CHANNEL C FOR A RESONANCE
      DEN          = ((ER - E)**2 + (GAM/2)**2)

      SUMMED OVER RESONANCES FOR EACH (L,J) SEQUENCE.

    """
    NE = len(E)         # number of energies
    dim = len(widths)   # dimension of matrix at each energy
    try:
        # use wrapped c version if available:
        import getScatteringMatrices
        # convert any constant width/penetrability data to array w/correct dimensions:
        nRes = len(Eres)
        for i1 in range(dim):
            if len(widths[i1]) != nRes:
                widths[i1] = numpy.ones((1,nRes)) * widths[i1][0,0]
            if len(penetrabilities[i1]) != NE:
                penetrabilities[i1] = numpy.ones((NE,1)) * penetrabilities[i1][0,0]
        R, S = getScatteringMatrices.getScatteringMatrices( E, Eres.copy(), captureWidth,
                numpy.array(widths), numpy.array(penetrabilities) )
    except ImportError:
        # can't import c version, so use numpy (memory-intensive)
        # define some common factors.
        # These are all 2d arrays with len(E) rows, len(Eres) columns:
        dE = Eres - E
        DEN = 1/(dE**2 + captureWidth**2)
        captOverDEN = captureWidth*DEN
        dEoverDEN = dE*DEN
        del dE, DEN

        R = numpy.zeros((NE,dim,dim))
        S = numpy.zeros((NE,dim,dim))
        for i in range(dim):
            for j in range(i,dim):
                width_ij = widths[i]*widths[j]
                p_ij = penetrabilities[i]*penetrabilities[j]
                R[:,i,j] = p_ij.T * numpy.sum( width_ij * captOverDEN , axis=1)
                S[:,i,j] = p_ij.T * numpy.sum( width_ij * dEoverDEN , axis=1)
                # symmetrize:
                R[:,j,i] = R[:,i,j]
                S[:,j,i] = S[:,i,j]
        del captOverDEN, dEoverDEN

    return R,S


def invertMatrices( R, S ):
    """
    find RI and SI such that (I+R+jS)*(I+RI+jSI) = I,
    where I is the identity matrix, and j = sqrt(-1)

    for more info, see comments for subroutine FROBNS3 in recent.f
    """
    assert R.shape == S.shape
    NE,dim,dim = R.shape

    if dim==1:
        # only have neutron width (and 'eliminated' capture width).
        # Can obtain quicker solution by manually inverting:
        DET = (R+1)**2 + S**2
        SI = -S/DET
        RI = -(R*(R+1)+S**2)/DET
        return RI,SI
    else:
        # have competition and/or fission, must invert matrices:
        def dotproduct(*args):
            # helper function: dotproduct(A,B,C) == numpy.dot(A, numpy.dot(B,C))
            def quickdot(a,b):
                # take dot product of two Nx(MxM) arrays (containing MxM matrices):
                result = numpy.zeros( a.shape )
                dim = a.shape[1]
                for i in range(dim):
                    for j in range(dim):
                        result[:,i,j] = numpy.sum( a[:,i,:] * b[:,:,j], axis=1 )
                return result
            return reduce( quickdot, args )

        def vectorInv(arr):
            # invert all MxM matrices in Nx(MxM) array
            dim = arr.shape[1]
            if dim==2:
                arrinv = numpy.zeros(arr.shape)
                det = (arr[:,0,0]*arr[:,1,1]-arr[:,0,1]*arr[:,1,0])
                arrinv[:,0,0] = arr[:,1,1]/det
                arrinv[:,0,1] = -arr[:,0,1]/det
                arrinv[:,1,0] = -arr[:,1,0]/det
                arrinv[:,1,1] = arr[:,0,0]/det
                return arrinv
            elif dim==3:
                arrinv = numpy.zeros(arr.shape)
                det = (arr[:,0,0]*(arr[:,1,1]*arr[:,2,2]-arr[:,1,2]*arr[:,2,1])
                    -arr[:,0,1]*(arr[:,1,0]*arr[:,2,2]-arr[:,1,2]*arr[:,2,0])
                    +arr[:,0,2]*(arr[:,1,0]*arr[:,2,1]-arr[:,1,1]*arr[:,2,0]) )
                arrinv[:,0,0] = (arr[:,1,1]*arr[:,2,2]-arr[:,1,2]*arr[:,2,1])/det
                arrinv[:,0,1] = (arr[:,0,2]*arr[:,2,1]-arr[:,1,0]*arr[:,2,2])/det
                arrinv[:,0,2] = (arr[:,0,1]*arr[:,1,2]-arr[:,0,2]*arr[:,1,1])/det
                arrinv[:,1,0] = (arr[:,1,2]*arr[:,2,0]-arr[:,1,0]*arr[:,2,2])/det
                arrinv[:,1,1] = (arr[:,0,0]*arr[:,2,2]-arr[:,0,2]*arr[:,2,0])/det
                arrinv[:,1,2] = (arr[:,0,2]*arr[:,1,0]-arr[:,0,0]*arr[:,1,2])/det
                arrinv[:,2,0] = (arr[:,1,0]*arr[:,2,1]-arr[:,1,1]*arr[:,2,0])/det
                arrinv[:,2,1] = (arr[:,0,1]*arr[:,2,0]-arr[:,0,0]*arr[:,2,1])/det
                arrinv[:,2,2] = (arr[:,0,0]*arr[:,1,1]-arr[:,0,1]*arr[:,1,0])/det
                return arrinv
            else:
                result = numpy.zeros( arr.shape )
                NE = arr.shape[0]
                for i in range(NE):
                    result[i] = numpy.linalg.inv(arr[i])
                return result

        identity = numpy.zeros( (NE, dim, dim) )
        for i in range(dim):
            identity[:,i,i] = 1

        invRplusI = vectorInv( R + identity )
        SRS = dotproduct( S, invRplusI, S )
        RI = dotproduct( -vectorInv( R+identity + SRS ), R+SRS )
        SI = dotproduct( -invRplusI, S, RI+identity )
        return RI, SI


#### Reich_Moore ####
class RMcrossSection(RRBaseClass):
    """
    simplified Reich_Moore (LRF=3 in ENDF)
    More complex than Breit-Wigner approximations, but we can still use same __init__
    """

    def __init__(self, reactionSuite, sectionIndex=None, enableAngDists=False, verbose=False, **kw):
        super(RMcrossSection, self).__init__(reactionSuite, sectionIndex, **kw)
        self.verbose = verbose
        self.sortLandJ()
        if self.verbose:
            print ("From %f to %f eV, reconstructing using Reich_Moore (LRF=3)" %
                    (self.lowerBound,self.upperBound))
        if enableAngDists: self.setResonanceParametersByChannel( useReichMooreApproximation = True )

    def getChannelConstantsBc( self ):
        """
        For ENDF's Reich-Moore, should be

            ..math::
                B_c = -\ell

        where $ell$ is the channel angular momentum

        what is not clearly stated in the ENDF manual is that Bc = 0 for this case
        """
        return [ 0.0 for c in self.channels ]

    def getL0Matrix( self, Ein, Bc=None ):
        """
        Get the L0 matrix of Froehner:

            ..math::

                {\bf L^0}_{cc'} = \delta_{cc'} (L_c-B_c)

        where

            ..math::

                L_c = S_c + i P_c

        But.... ENDF's RM formulation uses a shift of 0 and a Bc of 0!!!

        """
        L0 = numpy.zeros( (len(Ein), self.nChannels, self.nChannels), dtype=complex )
        for ic,c in enumerate(self.channels):
            L0[:,ic,ic] = (1j*self.penetrationFactor( c.l, self.rho( Ein, c.l ) )).flatten()
        return L0

    def getRMatrix( self, Ein ):
        """
        The R matrix in the Reich-Moore approximation,
        :math:`R_{cc'} = \sum_\lambda \frac{\gamma_{\lambda c}\gamma_{\lambda c'}{E_\lambda - E - i\Gamma_{\lambda\gamma}/2}`
        """

        R = numpy.zeros( (len(Ein), self.nChannels, self.nChannels), dtype=complex )

        # Loop through all resonances
        for iR, ER in enumerate( self._energies ):

            # Extract the gamma width for the first gamma channel that has this resonance
            gamWidth = 0.0
            for cg in self.eliminatedChannels:
                if iR in self.eliminatedChannels[ cg ]:
                    gamWidth = self.eliminatedChannels[ cg ][ iR ]
                    if gamWidth != 0.0: break
            if gamWidth == 0.0:
                print self.eliminatedChannels
                raise ValueError("Can't find gamma for resonance at ER = "+str(ER)+" eV")

            # Precompute the reduced widths
            redWidth = []
            for c in self.channels:
                if iR in self.channels[ c ]:
                    if c.reaction == 'elastic': pen = self.penetrationFactor( c.l, self.rho( abs( ER ), c.l ) )
                    else:                       pen = 1.0
                    redWidth.append( numpy.copysign( numpy.sqrt( abs( self.channels[ c ][ iR ] ) /
                        ( 2.0*abs( pen ) ) ), self.channels[ c ][ iR ] ) )
                else: redWidth.append( 0.0 )

            # Loop through all channels to accumulate the R Matrix elements
            for ic1, c1 in enumerate( self.channels ):
                if not iR in self.channels[ c1 ]: continue
                for ic2, c2 in enumerate( self.channels ):
                    if ic2 > ic1: break     # matrix is symmetric
                    if not iR in self.channels[ c2 ]: continue
                    if numpy.any(ER-Ein == 0.0) and gamWidth == 0.0:
                        raise ValueError( 'yikes! %s  vs.  %s'%(str(c1),str(c2)))
                    dR = (redWidth[ ic1 ] * redWidth[ ic2 ] / ( ER-Ein - 1j * gamWidth / 2.0 ))
                    R[:, ic1, ic2] += dR[:,0]
                    if ic1 != ic2:
                        R[:, ic2, ic1] += dR[:,0]

        return R

    @blockwise
    def getCrossSection(self, E):
        elasticSum = 0
        absorbtionSum = 0
        fissionSum = 0
        haveFission = self.RR.resonanceParameters.table.getColumn('fissionWidthA',units='eV') is not None
        # for calculating phi, always use tabulated scattering radius:
        for L in self.Ls:
            l = L['L']
            rho = self.rho(E,l)
            rhohat = self.RR.scatteringRadius.getValueAs('10*fm', L=l) * self.k(E)
            phi = self.phi(l, rhohat)
            P = numpy.sqrt( self.penetrationFactor(l,rho) )

            for J in L['Js']:
                gfactor = J['gfact']
                for spin in J['channelSpins']:
                    captureWidth = spin['captureWidth'] * 0.5
                    widths = []
                    penetrabilities = []
                    # FIXME note that spin['neutronWidth'] already includes the penetrablity (calculated at resonances)
                    # That got wrapped in during sortLandJ, but may wish to move it back to here for readability
                    widths.append( numpy.sqrt( spin['neutronWidth'] * 0.5 ) )
                    penetrabilities.append(P)
                    if haveFission:
                        fissWidthA = numpy.sqrt(numpy.abs(spin['fissionWidthA'] * 0.5))
                        fissWidthB = numpy.sqrt(numpy.abs(spin['fissionWidthB'] * 0.5))
                        fissWidthA[ spin['fissionWidthA']<0 ] *= -1
                        fissWidthB[ spin['fissionWidthB']<0 ] *= -1
                        widths += [fissWidthA, fissWidthB]
                        penetrabilities += [numpy.array([[1]]),numpy.array([[1]])]

                        RI,SI = invertMatrices(
                                *getR_S(E, spin['energy'], captureWidth, widths, penetrabilities)
                                )

                        elasticSum += gfactor * ((2*numpy.sin(phi[:,0])**2+2*RI[:,0,0])**2 +
                                (2*numpy.sin(phi[:,0])*numpy.cos(phi[:,0]) + 2*SI[:,0,0])**2)
                        absorbtionSum += -4*gfactor * (RI[:,0,0]+RI[:,0,0]**2+SI[:,0,0]**2)
                        fissionSum += 4*gfactor * (RI[:,0,1]**2+RI[:,0,2]**2+SI[:,0,1]**2+SI[:,0,2]**2)

                    else: # faster method when we don't have fission:
                        RI, SI = invertMatrices(
                                *getR_S(E, spin['energy'], captureWidth, widths, penetrabilities)
                                )
                        RI, SI = numpy.squeeze(RI), numpy.squeeze(SI)
                        elasticSum += gfactor * ((2*numpy.sin(phi[:,0])**2+2*RI)**2 +
                                (2*numpy.sin(phi[:,0])*numpy.cos(phi[:,0]) + 2*SI)**2)
                        absorbtionSum += -4*gfactor * (RI + RI**2 + SI**2)

            if True: #addMissingGfactor:
                elasticSum += 2*numpy.sin(phi[:,0])**2 * 2*self.missingGfactor[l]

        # get common factor 'beta' as a row vector:
        beta = numpy.pi / self.k(E)[:,0]**2
        elastic = beta * elasticSum
        absorbtion = beta * absorbtionSum
        fission = beta * fissionSum
        capture = absorbtion - fission
        total = elastic + absorbtion

        return {'total':total, 'elastic':elastic, 'capture':capture, 'fission':fission, 'nonelastic':absorbtion}


#### R-Matrix Limited ####
class RMatrixLimitedcrossSection(RRBaseClass):
    """
    extended Reich_Moore (LRF=7 in ENDF)
    Here, resonances are sorted primarily by J: within each 'spin group', total J is conserved
    One or more competitive channels may be used in this case.
    Also, each resonance may have contributions from multiple l-waves
    """

    def __init__(self, reactionSuite, sectionIndex=None, enableAngDists=False, verbose=True, **kw):
        super(RMatrixLimitedcrossSection, self).__init__(reactionSuite, sectionIndex, **kw)
        self.verbose = verbose
        if self.verbose:
            print ("From %f to %f eV, reconstructing using R-Matrix Limited (LRF=7)" %
                    (self.lowerBound,self.upperBound))

        # for RML, need to know what residual nuclei are produced by each channel:
        thresholds = []
        for ch in self.RR.channels:
            reaction = reactionSuite.getReaction(ch.name)
            # elastic, capture or competitive?
            if reaction == reactionSuite.getReaction('capture'): ch.tag = 'capture'
            elif reaction == reactionSuite.getReaction('elastic'): ch.tag = 'elastic'
            elif 'fission' in ch.name: ch.tag = ch.name
            else: ch.tag = 'competitive'

            Q = ch.Q.getValueAs('eV')
            if not Q:
                Q = reaction.getQ('eV')
                # adjust Q value for residual in excited state:
                for particle in reaction.outputChannel.products:
                    if( hasattr( particle, 'getLevelAsFloat' ) ) : Q -= particle.getLevelAsFloat( 'eV' )
            # Xi = reaction threshold in the lab frame.
            targetToProjectileMassRatio = self.target.getMass('amu') / self.projectile.getMass('amu')
            Xi = - ( (targetToProjectileMassRatio+1) / targetToProjectileMassRatio ) * Q
            particles = reaction.outputChannel.products
            ch.reactionInfo = { 'Xi':Xi, 'particles': particles }
            if Xi > 0:
                thresholds.append(Xi)

        for sg in self.RR.spinGroups:
            sg.energy = numpy.array( sg.resonanceParameters.table.getColumn('energy','eV') )

            for column in sg.resonanceParameters.table.columns:
                if column.name=='energy': continue
                channelName = column.name.split(' width')[0]
                openChannel = [ch for ch in self.RR.channels if ch.name==channelName]
                assert len(openChannel)==1, ("Could not find unique openChannel named '%s'" % channelName)
                column.tag = openChannel[0].tag

        # for energy grid generation:
        energies, totalWidths = [],[]
        for sg in self.RR.spinGroups:
            energies.extend( sg.resonanceParameters.table.getColumn('energy','eV') )
            widths = [sg.resonanceParameters.table.getColumn( col.name, 'eV' ) for col in
                    sg.resonanceParameters.table.columns if col.name != 'energy']
            totalWidths.extend( numpy.sum( widths, axis=0 ) )
        zipped = sorted(zip(energies,totalWidths))
        self._energies, self._widths = zip(*zipped)
        self._thresholds = thresholds

        if enableAngDists: self.setResonanceParametersByChannel()

    def getScatteringLength(self):
        '''
        Compute R' in b**1/2, should be close to AP

        The potential scattering cross section sigPot = 4 Pi (R')^2, so we compute the potential scattering cross section at E=1e-5 eV
        :return:
        '''
        E=[1e-5]
        sigPotL = []
        for c in self.channels:
            if not c.isElastic: continue
            sigPotL.append( ( ( 2.0 * c.l + 1 ) ) * 4.0 * numpy.pi * ( numpy.sin( self.phi( c.l, self.rhoat(E,c) ) ) )**2 / self.k(E)**2 )
        print sigPotL
        sigPot = sum(sigPotL)
        return numpy.sqrt(sigPot/4.0/numpy.pi)

    def isElastic(self, reactionDesignator):
        rs = self.RR.getRootAncestor()
        return rs.getReaction(reactionDesignator) == rs.getReaction('elastic')

    def getLMax(self, maxLmax=10):
        """
        LMax is determined by the behavior of the Blatt-Biedenharn Zbar coefficients.  Inside each one, there is
        a Racah coefficient and a Clebsh-Gordon coefficient.  The CG coefficient looks like this:
                ( l1 l2  L )
                (  0  0  0 )
        So, this means two things.  First, the CG coeff (and hence Zbar) will be zero if l1+l2+L=odd.
        Second, the maximum value of L will be l1max+l2max.  Hence, Lmax=2*lmax.
        """
        return min( max( [ 2*c.l for c in self.channels ] ), maxLmax )

    def setResonanceParametersByChannel( self, multipleSScheme='NJOY', useReichMooreApproximation=False, Ein=None ):
        """
        Reorganize member data into channels
        :param multipleSScheme:  ignored, kept so has same signature as overridden function
        :param useReichMooreApproximation:  ignored, kept so has same signature as overridden function
        :return:
        """
        self.nResonances = sum( [ len( sg.resonanceParameters.table ) for sg in self.RR.spinGroups ] )
        self.JMax = max( [sg.spin for sg in self.RR.spinGroups] )
        self.channelConstantsBc = []
        self.particlePairs=collections.OrderedDict()
        self.scatteringRadiiTrue = None
        self.scatteringRadiiEffective = None
        self.overrides=collections.OrderedDict()
        allowedSs = getAllowedTotalSpins( 0.5, self.spin, useFactor2Trick=False )

        # The unified table of resonance parameter data
        channelDict = collections.OrderedDict()
        def addOrUpdateDict( theDict, theKey, theValue ):
            if not theKey in theDict: theDict[ theKey ] = {}
            theDict[ theKey ][ theValue[0] ] = theValue[1]

        # Pack the channels
        channelIndex=0
        for sg in self.RR.spinGroups:
            ERs = sg.resonanceParameters.table.getColumn( sg.resonanceParameters.table.columns[0].name, sg.resonanceParameters.table.columns[0].units )
            for col in sg.resonanceParameters.table.columns:
                if col.name == 'energy': continue # skip this column....
                eliminatedChannel = self.RR.approximation == 'Reich_Moore' and 'gamma' in col.name

                if not eliminatedChannel:
                    # Check the validity of all angular momenta
                    if sg.spin.value not in getAllowedTotalSpins( col.attributes['L'], col.attributes["channelSpin"], useFactor2Trick=False ):
                        raise ValueError( 'Invalid spin combination: cannot couple L = %s and S = %s up to J = %s for "%s"'% (str(col.attributes['L']), str(col.attributes["channelSpin"]), str(sg.spin), col.name ) )

                # Look up the particle pair
                ppFound=False
                for pp in self.RR.channels:
                    if ' '.join(col.name.split()[:-1]) == pp.name:
                        ppFound=True
                        break
                if not ppFound: raise KeyError( "Could not find particle pair to match '%s'"%col.name)

                # Construct the channel designator
                gfact = (2.0*abs(sg.spin.value)+1)/(2*(2*float(self.spin)+1))
                ps0=str(pp.reactionInfo['particles'][0])
                ps1=str(pp.reactionInfo['particles'][1])
                if 'gamma' in [ps0,ps1]:   channelClass = GAMMACHANNEL
                elif 'n'  in [ps0,ps1]:    channelClass = NEUTRONCHANNEL
                elif 'fission' in ps0+ps1: channelClass = FISSIONCHANNEL
                else:                      channelClass = CPCHANNEL
                c=ChannelDesignator(
                     index=channelIndex,
                     reaction=pp.name,
                     l=col.attributes['L'],
                     s=col.attributes["channelSpin"],
                     J=sg.spin.value,
                     gfact=gfact,
                     particleA=ps0,
                     particleB=ps1,
                     Xi=pp.reactionInfo['Xi'],
                     isElastic=self.isElastic(pp.name),
                     channelClass=channelClass,
                     useRelativistic=self.RR.relativisticKinematics,
                     eliminated=eliminatedChannel )
                channelIndex+=1

                # Don't put closed channels onto lists
                if Ein is not None and not numpy.all(c.is_open(Ein)):
                    if numpy.any(c.is_open(Ein)):
                        print "WARNING: Rethink your grid!  Your grid straddles a threshold at %s eV for channel %s, l=%i, s=%i, J=%i."%(str(c.Xi),c.reaction,c.l,c.s,c.J)
                    continue

                # Save the particle pair, helps finding them later
                self.particlePairs[c]=pp

                # Log the overrides
                if pp.label in sg.overrides:
                    self.overrides[c]=sg.overrides[ pp.label ]
                else:
                    self.overrides[c]=None

                # Now do the actual resonance packing
                for iR, width in enumerate(sg.resonanceParameters.table.getColumn( col.name, col.units )):
                    addOrUpdateDict( channelDict, c, ( self._energies.index(ERs[iR]), width ) )

        # Set up the channel->resonance mappings
        self.allChannels = channelDict
        self.channels = collections.OrderedDict()  # just the kept ones
        self.eliminatedChannels = collections.OrderedDict()
        for c in self.allChannels:
            if c.eliminated:    self.eliminatedChannels[ c ] = self.allChannels[ c ]
            else:               self.channels[ c ] = self.allChannels[ c ]
        self.nChannels = len( self.channels )
        self.identityMatrix = numpy.identity( self.nChannels, dtype=complex )

    def resetResonanceParametersByChannel(self, multipleSScheme='NJOY', useReichMooreApproximation=False, Ein=None ):
        return self.setResonanceParametersByChannel( multipleSScheme=multipleSScheme, useReichMooreApproximation=useReichMooreApproximation, Ein=Ein )

    def getChannelConstantsBc( self ):
        """
        For ENDF's Reich-Moore, should be :math:`B_c = -\\ell`
        where :math:`\\ell` is the channel angular momentum, but the ENDF manual says nothing about it.

        There is a per-channel parameter BCH that we will interpret as :math:`B_c`
        """
        Bc=[]
        for c in self.channels:
            pp=self.particlePairs[c]
            if pp.boundaryCondition:
                Bc.append(pp.boundaryCondition)
            else:
                Bc.append(0.0)
        return Bc

    def getChannelScatteringRadiiTrue(self):
        APT=collections.OrderedDict()
        for c in self.channels:
            if self.RR.calculateChannelRadius:
                a = 0.123 * self.target.getMass('amu')**(1./3.) + 0.08
            elif self.overrides[c] is not None and self.overrides[c].scatteringRadius is not None:
                a = self.particlePairs[c].scatteringRadius.getValueAs('10*fm')
            else:
                a = self.particlePairs[c].scatteringRadius.getValueAs('10*fm')
            APT[c]=a
        return APT

    def getChannelScatteringRadiiEffective(self):
        APE=collections.OrderedDict()
        for c in self.channels:
            if self.overrides[c] is not None and self.overrides[c].effectiveRadius is not None:
                a = self.overrides[c].effectiveRadius.getValueAs('10*fm')
            elif self.particlePairs[c].effectiveRadius is not None:
                a = self.particlePairs[c].effectiveRadius.getValueAs('10*fm')
            else:
                a = self.particlePairs[c].scatteringRadius.getValueAs('10*fm')
            APE[c]=a
        return APE

    def rho(self, Ein, c):
        """
        Compute :math:`\\rho_c(E) = a_c * k_c(E)`, using the true scattering radius.
        ENDF uses it for calculating shift and penetrabilities.

        :param Ein: incident energy in the lab frame (shifted by a threshold, if appropriate)
        :param c: the channel designator
        :return: the value of rho (dimensionless)
        """
        if self.scatteringRadiiTrue is None: self.scatteringRadiiTrue = self.getChannelScatteringRadiiTrue()
        pA,pB = self.particlePairs[c].reactionInfo['particles']
        return self.k_competitive(Ein, pA, pB) * self.scatteringRadiiTrue[c] # dimensionless

    def rhohat(self, Ein, c):
        """
        Compute :math:`\\hat{\\rho}_c(E) = a_c * k_c(E)`, using the effective scattering radius
        ENDF uses it for calculating the phase (but in truth, there should be no effective scattering radius).
        (Caleb uses self.k below, but I think it should be self.k_competitive for the sake of consistency)

        :param Ein: incident energy in the lab frame (shifted by a threshold, if appropriate)
        :param c: the channel designator
        :return: the value of rho (dimensionless)
        """
        if self.scatteringRadiiEffective is None: self.scatteringRadiiEffective = self.getChannelScatteringRadiiEffective()
        pA,pB = self.particlePairs[c].reactionInfo['particles']
        return self.k_competitive(Ein, pA, pB) * self.scatteringRadiiEffective[c] # dimensionless

    def omega(self,eta,L):
        if L > 0: return sum( [numpy.arctan2(eta,n) for n in range(1,L+1)] )
        return numpy.zeros_like(eta)

    def getL0Matrix( self, Ein ):
        """
        Get the :math:`L^0` matrix of Froehner, :math:`{\\bf L^0}_{cc'} = \\delta_{cc'} (L_c-B_c)`
        where :math:`L_c = S_c + i P_c`

        """
        if not hasattr(self,'channelConstantsBc') or self.channelConstantsBc == []:
            self.channelConstantsBc = self.getChannelConstantsBc()
        L0 = numpy.zeros( (len(Ein), self.nChannels, self.nChannels), dtype=complex )

        for ic,c in enumerate(self.channels):
            if c.channelClass in [FISSIONCHANNEL, GAMMACHANNEL]:
                shift = 0.0
                penet = 1.0
            elif c.channelClass == CPCHANNEL:
                import getCoulombWavefunctions
                rho = self.rho(Ein-c.Xi, c)
                pA, pB = self.particlePairs[c].reactionInfo['particles']
                eta = self.eta(Ein-c.Xi, pA, pB)
                shift = getCoulombWavefunctions.coulombShiftFactor(c.l,rho,eta)
                penet = getCoulombWavefunctions.coulombPenetrationFactor(c.l,rho,eta)
            else:
                rho = self.rho(Ein-c.Xi, c)
                penet = self.penetrationFactor(c.l, rho)
                shift = self.shiftFactor(c.l, rho)

            # ENDF appears to set Bc = Sc most of the time.  When that's not the case,
            # Bc is set to something non zero, so in that case, compute L0 correctly
            if self.channelConstantsBc[ ic ] != 0.0:
                L0[:,ic,ic] = (shift + 1j*penet - self.channelConstantsBc[ ic ]).flatten()
            else:
                L0[:,ic,ic] = (1j*penet).flatten()
        return L0

    def getRMatrix( self, Ein ):
        """
        The R matrix in the Reich-Moore approximation is :math:`R_{cc'}=\\sum_\\lambda{\\gamma_{\\lambda c}\\gamma_{\\lambda c'}/({E_\\lambda - E - i\\Gamma_{\\lambda\\gamma}/2})`

        :param Ein:
        :type Ein: numpy.array(type=float)
        :return:
        :rtype:
        """
        R = numpy.zeros( (len(Ein), self.nChannels, self.nChannels), dtype=complex )

        # Loop through all resonances
        for iR, ER in enumerate( self._energies ):

            # Extract the gamma width for the first gamma channel that has this resonance
            gamWidth = 0.0
            for cg in self.eliminatedChannels:
                if iR in self.eliminatedChannels[ cg ]:
                    gamWidth = self.eliminatedChannels[ cg ][ iR ]
                    if gamWidth != 0.0: break

            # Precompute the reduced widths
            redWidth = []
            for ic,c in enumerate(self.channels):
                if iR in self.channels[c] and self.channels[c][iR] != 0.0:
                    width = self.channels[c][iR]
                    shiftedER=numpy.array([abs(ER-c.Xi)])
                    rho = self.rho(shiftedER, c)
                    if c.channelClass == NEUTRONCHANNEL:
                        pen = self.penetrationFactor( c.l, rho )
                    elif c.channelClass == CPCHANNEL:
                        pA, pB = self.particlePairs[c].reactionInfo['particles']
                        eta = self.eta(shiftedER, pA, pB)
                        pen = getCoulombWavefunctions.coulombPenetrationFactor(c.l, rho, eta)
                        if numpy.isnan(pen):
                            if VERBOSE: print iR, ER-c.Xi, c.l, rho, eta, width
                            raise ValueError('pen=%s for channel %s and resonance #%i, but L0[%i,%i]=%s '%(str(pen),str(c),iR,ic,ic,str(self.getL0Matrix(Ein-c.Xi)[:,ic,ic])))
                    else: pen = 1.0
                    if pen != 0.0:
                        redWidth.append( numpy.copysign( numpy.sqrt(numpy.abs(width/2.0/pen)), width )[0] )
                    else:
                        if VERBOSE: print iR, ER-c.Xi, c, rho, eta, width
                        redWidth.append( 0.0 )
                else:   redWidth.append( 0.0 )

            # Loop through all channels to accumulate the R Matrix elements
            for ic1, c1 in enumerate( self.channels ):
                if not iR in self.channels[ c1 ]: continue
                for ic2, c2 in enumerate( self.channels ):
                    if ic2 > ic1: break     # matrix is symmetric
                    if not iR in self.channels[ c2 ]: continue
                    dR = (redWidth[ ic1 ] * redWidth[ ic2 ] / ( ER-Ein - 1j * gamWidth / 2.0 ))
                    if any( numpy.isnan(dR) ):
                        if VERBOSE: print redWidth
                        raise ValueError('nan in R-matrix for channels %s and %s '%(str(c1),str(c2)))
                    R[:, ic1, ic2] += dR[:,0]
                    if ic1 != ic2:
                        R[:, ic2, ic1] += dR[:,0]
        return R

    def getScatteringMatrixT( self, Ein, useTabulatedScatteringRadius=True, enableExtraCoulombPhase=False ):
        """

        :param Ein:
        :type Ein: numpy.array(type=float)
        :param useTabulatedScatteringRadius:
        :type useTabulatedScatteringRadius: bool
        :param enableExtraCoulombPhase:
        :type enableExtraCoulombPhase: bool
        :return:
        :rtype:
        """
        # Make sure all channels are open at all requested energies
        if not numpy.all([c.is_open(Ein) for c in self.channels]): raise ValueError("One or more channels are not open on all energies in requested energy grid")

        T = numpy.zeros( ( len(Ein), self.nChannels, self.nChannels ), dtype=complex )
        U = self.getScatteringMatrixU( Ein,
                                       useTabulatedScatteringRadius=useTabulatedScatteringRadius,
                                       enableExtraCoulombPhase=enableExtraCoulombPhase )
        for ic1, c1 in enumerate( self.channels ):
            pA, pB = self.particlePairs[c1].reactionInfo['particles']
            eta = self.eta(Ein-c1.Xi, pA, pB)
            wc  = self.omega(eta,c1.l)
            for ic2 in range( self.nChannels ):
                if enableExtraCoulombPhase:
                    if ic1==ic2: eTwoIWcDeltacc=numpy.exp(2j*wc).flatten()
                    else:        eTwoIWcDeltacc=0.0j
                    T[:, ic1, ic2] = eTwoIWcDeltacc  - U[:, ic1, ic2]
                else:
                    T[:, ic1, ic2] = float(ic1==ic2) - U[:, ic1, ic2]
        return T

    def getEiPhis( self, Ein, useTabulatedScatteringRadius=None, enableExtraCoulombPhase=False ):
        """
        The phase factor for the collision matrix, :math:`\\Omega_c=e^{\\omega_c-\\varphi_c}`

        :param Ein:
        :type Ein: numpy.array(type=float)
        :param useTabulatedScatteringRadius:
        :type useTabulatedScatteringRadius: bool
        :param enableExtraCoulombPhase:
        :type enableExtraCoulombPhase: bool
        :return:
        :rtype:
        """
        # Precompute phase factor
        eiphis = []
        for ic, c in enumerate( self.channels ):
            if c.channelClass in [FISSIONCHANNEL, GAMMACHANNEL]:
                eiphis.append( numpy.ones( Ein.shape, dtype=complex ) )
            elif c.channelClass == CPCHANNEL:
                import getCoulombWavefunctions
                rho = self.rhohat(Ein-c.Xi, c)
                pA, pB = self.particlePairs[c].reactionInfo['particles']
                eta = self.eta(Ein-c.Xi, pA, pB)
                phic = getCoulombWavefunctions.coulombPhi( c.l, rho, eta ).flatten()
                if numpy.any(numpy.isnan(phic)):
                    raise ValueError('phi is NaN for channel %s: %s '%(str(c),str(zip(Ein.flatten()-c.Xi,phic.flatten()))))
                if enableExtraCoulombPhase:
                    wc = self.omega(eta,c.l).flatten()
                    eiphis.append( numpy.exp( 1j * wc.flatten() - 1j * phic.flatten() ) )
                else:
                    eiphis.append( numpy.exp( -1j * phic.flatten() ) )
            else:
                rho = self.rhohat(Ein-c.Xi, c)
                phic = self.phi( c.l, rho )
                eiphis.append( numpy.exp( -1j * phic.flatten() ) )
        return eiphis

    def k_competitive(self, Ex, pA, pB):
        """
        Calculate k for any 2-body output channel.

        Note that if pA and pB are target and neutron, this reduces to self.k(E) as defined above
        in the resonanceReconstructionBaseClass

        :param Ex: incident energy - Xi (Xi is the lab frame reaction threshold) in eV
        :param pA: xParticle A
        :param pB: xParticle B
        :return: k in b**-1/2
        """
        pA_mass, pB_mass = [p.particle.getMass('amu') for p in pA,pB]
        mn = self.projectile.getMass('amu')
        targ_mass = self.target.getMass('amu')
        # sqrt(2*neutronMass)/hbar == 2.196807 (eV*barn)**-1/2. Thus for energy in eV, k is in b**-1/2
        # FIXME: remove cancelling mn/mn (one shows up inside the numeric constant)
        return 2.196807122623e-3 * numpy.sqrt( pA_mass * pB_mass / (pB_mass + pA_mass) / mn *
                targ_mass / (targ_mass + mn) ) * numpy.sqrt(Ex)

    def eta(self, Ex, pA, pB):
        """
        eta, the  Sommerfeld parameter, given by :math:`\\eta = Z_A Z_B m_{red} \\alpha / ( \\hbar c k )`

        for competitive channels with 2 charged particles, parameter eta is used to find penetrability.
        eta is given in eq D.79 of ENDF manual and $e^2$ is the fine structure constant $\alpha$ and
        $m_{red}$ is the reduced mass.  eta is dimensionless.

        :param Ex: The incident energy [eV]
        :param pA: xParticle A
        :param pB: xParticle B
        :return:   the Sommerfeld parameter [dimensionless]
        """
        pA_z, pB_z = [p.particle.getZ_A_SuffixAndZA()[0] for p in pA, pB]
        if pA_z * pB_z == 0: return numpy.zeros_like(Ex)
        pA_mass, pB_mass = [p.particle.getMass('amu') for p in pA,pB]
        mn = self.projectile.getMass('amu')
        eSq_over_hbarSq = 3.4746085579272e-1    # ?, should be b**-1/2
        k_comp = self.k_competitive(Ex, pA, pB) # in b**-1/2
        eta = (eSq_over_hbarSq * pA_z * pB_z * (pA_mass/mn) * (pB_mass/(pB_mass+pA_mass)) / k_comp)
        return eta

    @blockwise
    def getCrossSection(self, E):
        """
        similar to Reich_Moore (LRF=3). Refer to comments there, and in
        subroutine SIGRM2 in recent.f
        """
        elasticSum = 0
        absorbtionSum = 0
        fissionSum = 0
        nCompetitive = len( [ch for ch in self.RR.channels if ch.tag=='competitive'] )
        competitiveSum = [0,] * nCompetitive
        haveFission = any(['fission' in a.name for a in self.RR.channels])

        for sg in self.RR.spinGroups:
            j = sg.spin.value
            gfact = (2*j+1.0)/(2*(2*self.spin+1))

            widths = []
            penetrabilities = []
            phis = []    # phi is l-dependant
            Xis = []
            thresholdIndices = []
            for chan in sg.resonanceParameters.table.columns:
                if chan.name=='energy': continue
                chanWidths = numpy.array( sg.resonanceParameters.table.getColumn( chan.name, 'eV' ) )
                channelName = chan.name.split(' width')[0]
                parentChannel, = [ch for ch in self.RR.channels if ch.name == channelName]
                override = None
                if parentChannel.label in sg.overrides:
                    override = sg.overrides[ parentChannel.label ]

                if chan.tag == 'capture':
                    captureWidth = chanWidths / 2
                    continue
                # else:
                l = chan['L']
                pA,pB = parentChannel.reactionInfo['particles']
                Xi = parentChannel.reactionInfo['Xi']
                Xis.append( Xi )

                if Xi>0:
                    # find index of first incident energy above threshold:
                    import bisect
                    thresholdIndex = bisect.bisect( E, Xi )
                else:
                    thresholdIndex = 0
                thresholdIndices.append( thresholdIndex )

                # channel radius:
                def rho( Ex ):
                    if self.RR.calculateChannelRadius:
                        a = 0.123 * self.target.getMass('amu')**(1./3.) + 0.08
                    elif override is not None and override.scatteringRadius is not None:
                        a = override.scatteringRadius.getValueAs('10*fm')
                    else:
                        a = parentChannel.scatteringRadius.getValueAs('10*fm')
                    return self.k_competitive(Ex, pA, pB) * a

                # rhohat, for calculating phase shift phi:
                if override is not None and override.effectiveRadius is not None:
                    rhohat = override.effectiveRadius.getValueAs('10*fm') * self.k(E)
                elif parentChannel.effectiveRadius is not None:
                    rhohat = parentChannel.effectiveRadius.getValueAs('10*fm') * self.k(E)
                else:
                    rhohat = parentChannel.scatteringRadius.getValueAs('10*fm') * self.k(E)
                phinow = self.phi(l, rhohat)
                phinow[ phinow/rhohat < 1e-6 ] = 0  # see subroutine 'facphi' in RECENT
                phis.append( phinow )

                # penetrability:
                Ex1 = abs(abs(sg.energy)-Xi)    # evaluated at resonances
                Ex2 = E-Xi; Ex2[Ex2<0] = 0      # evaluated at each incident energy
                eta1 = self.eta(Ex1, pA, pB)
                if any(eta1 > 0):
                    # output channel has two charged particles, need Coulomb penetrability:
                    penetrabilityAtResonances = getCoulombWavefunctions.coulombPenetrationFactor(l, rho(abs(Ex1)), eta1)
                    if thresholdIndex > 0:  # threshold reaction
                        eta2 = numpy.zeros_like( Ex2 )
                        eta2[ thresholdIndex: ] = self.eta( Ex2[ thresholdIndex: ], pA, pB )

                        penetrabilityAtEin = numpy.zeros_like( Ex2 )
                        penetrabilityAtEin[ thresholdIndex: ] = numpy.sqrt(
                                getCoulombWavefunctions.coulombPenetrationFactor(l, rho(Ex2[ thresholdIndex: ]),
                                eta2[ thresholdIndex: ] ) )

                    else:
                        eta2 = self.eta(Ex2, pA, pB)
                        penetrabilityAtEin = numpy.sqrt( getCoulombWavefunctions.coulombPenetrationFactor(l,rho(Ex2), eta2) )
                else:
                    # no Coulomb contribution:
                    penetrabilityAtResonances = self.penetrationFactor(l, rho(abs(Ex1)))
                    penetrabilityAtEin = numpy.sqrt( self.penetrationFactor(l, rho(Ex2)) )

                reducedWidths = numpy.sqrt( abs(chanWidths) / (2 * penetrabilityAtResonances) )
                reducedWidths[ chanWidths<0 ] *= -1
                widths.append( reducedWidths )
                penetrabilities.append( penetrabilityAtEin )

            # are there any threshold reactions (negative Q-values)?
            # If so, we must break up the calculation above/below each threshold
            if any( thresholdIndices ):
                thresholdIndices.append( len(E) )
                # sanity check: channels should be sorted by increasing threshold
                assert thresholdIndices==sorted(thresholdIndices)

                RI = numpy.zeros((len(E), len(widths), len(widths)))
                SI = numpy.zeros( RI.shape )

                threshSet = sorted(set(thresholdIndices))
                for i1 in range(len(threshSet)-1):
                    low = threshSet[i1]
                    high = threshSet[i1+1]
                    nOpen = len( [th for th in thresholdIndices if th-low <= 0] )
                    RI_now, SI_now = invertMatrices(
                            *getR_S( E[low:high], sg.energy, captureWidth,
                            widths[:nOpen], [p[low:high] for p in penetrabilities[:nOpen]] )
                            )
                    if nOpen==1:  # numpy insists on same number of dimensions for copy:
                        RI_now.shape = SI_now.shape = (len(RI_now),1,1)

                    RI[low:high, :nOpen, :nOpen] = RI_now
                    SI[low:high, :nOpen, :nOpen] = SI_now

            else:   # no threshold reactions
                RI,SI = invertMatrices(
                        *getR_S(E, sg.energy, captureWidth, widths, penetrabilities)
                        )

            # reconstruct:
            chanIds = []
            for col in sg.resonanceParameters.table.columns:
                if col.name=='energy' or col.tag=='capture': continue
                index, thisChannel = [ch for ch in enumerate(self.RR.channels) if
                        ch[1].name==col.name.split(' width')[0] ][0]
                chanIds.append( index )
            chanIds = numpy.array( chanIds )
            elasID = [int(tmp.label) for tmp in self.RR.channels if tmp.tag=='elastic'][0] # should be '1'
            competitiveIDs = [tmp.label for tmp in self.RR.channels if tmp.tag=='competitive']
            for chan in self.RR.channels:
                if chan.tag == 'capture':
                    continue    # 'eliminated' channel in Reich_Moore
                # which matrix elements correspond to this channel?
                thisChanIds = numpy.where( chanIds==int(chan.label) )[0]
                if len(thisChanIds)==0:
                    continue
                id1, id2 = min(thisChanIds), max(thisChanIds)+1
                assert len(thisChanIds) == id2-id1
                if chan.tag == 'elastic':
                    elas = 0; absorb = 0
                    # diagonal component
                    for i in range(id1,id2):
                        phi = phis[i] [:,0] # convert to row vector
                        sinsqr = numpy.sin(phi)**2
                        sincos = numpy.sin(phi)*numpy.cos(phi)
                        elas += ( sinsqr * (sinsqr+2*RI[:,i,i]) + sincos * (sincos + 2*SI[:,i,i]) )
                        absorb += -RI[:,i,i]
                    # add cross-terms:
                    elas += numpy.sum(numpy.sum( RI[:,id1:id2,id1:id2]**2 + SI[:,id1:id2,id1:id2]**2,
                            axis=1), axis=1)
                    absorb -= numpy.sum(numpy.sum( RI[:,id1:id2,id1:id2]**2 + SI[:,id1:id2,id1:id2]**2,
                            axis=1), axis=1)
                    elasticSum += gfact * 4 * elas
                    absorbtionSum += gfact * 4 * absorb

                else: # competitive or fission:
                    # sum of cross-terms between this channel and elastic:
                    if 'fission' in chan.tag:
                        print ("      WARNING: haven't dealt with R-Matrix fission yet... proceed with caution!")
                    elasticIds = numpy.where( chanIds==elasID )[0]
                    el1, el2 = min(elasticIds), max(elasticIds)+1
                    comp = numpy.sum(numpy.sum(SI[:,id1:id2,el1:el2]**2 + RI[:,id1:id2,el1:el2]**2,
                            axis=1),axis=1)
                    # may have more than one competitive: add to correct channel
                    competitiveSum[ competitiveIDs.index( chan.label ) ] += gfact * 4 * comp

        # get common factor 'beta' as a row vector:
        beta = numpy.pi / self.k(E)[:,0]**2
        elastic = beta * elasticSum
        absorbtion = beta * absorbtionSum
        total = elastic + absorbtion
        competitive = [ beta * comp for comp in competitiveSum ]
        fission = beta * fissionSum
        capture = absorbtion - fission - sum(competitive)

        retDict = {'total':total, 'elastic':elastic, 'capture':capture, 'fission':fission, 'nonelastic':absorbtion}
        competitiveNames = [ch.name for ch in self.RR.channels if ch.tag=='competitive']
        for key,val in zip(competitiveNames,competitive):
            retDict[ key ] = val
        return retDict


##### unresolved resonance region. Only one formalism here: #####
class URRcrossSection(resonanceReconstructionBaseClass):

    def __init__(self, reactionSuite, verbose=True, **kw):
        """
        Initialize the URR management class

        :param reactionSuite: The reactionSuite this class is destined to be part of
        :param verbose: duh, verbosity flag
        :param kw: Python dict of keywords, currently none defined
        :return: None
        """
        super(URRcrossSection,self).__init__(reactionSuite)
        self.verbose = verbose

        # energy boundaries for this region:
        urr = reactionSuite.resonances.unresolved
        self.reactionSuite = reactionSuite
        self.URR = urr.evaluated
        self.lowerBound = urr.lowerBound.getValueAs('eV')
        self.upperBound = urr.upperBound.getValueAs('eV')
        if self.verbose:
            print ("Unresolved from %f to %f eV" % (self.lowerBound,self.upperBound))
        self.levelSpacings=None
        self.averageWidths=None
        self.levelSpacingFuncs=None
        self.averageWidthFuncs=None
        self.DOFs=None
        self.egrid=None

    def getLastResolvedResonanceRegion(self):
        """
        Get the highest energy resonance ENDF region in the resolved resonance region (which may contain more than one ENDF region)

        :return: The ENDF resolved resonance region, or None if there is no ENDF region in the data
        """
        if self.reactionSuite.resonances.resolved:
            # For multiple regions, we need to do each region separately, then add them to the unified xs table & egrid
            if self.reactionSuite.resonances.resolved.multipleRegions:
                return self.reactionSuite.resonances.resolved.regions[-1].evaluated
            # Single region, everything goes on unified grid
            else:
                return self.reactionSuite.resonances.resolved.evaluated
        else: return None

    def getLastResolvedResonanceEnergy(self,l=None,j=None):
        """
        Get the last resonance energy from the resolved region, that will start all the ladders in the URR

        :param l: orbital angular momentum of the resonance to find
        :param j: total angular momentum of the resonance to find
        :return: either the energy of the last resonance with requested (l,j) or None if it can't be found
        """
        for x in reversed(self.getLastResolvedResonanceRegion().resonanceParameters.table):
            if x[1]==l and x[2]==j: return x[0]

        return None

    def getWidthsAndSpacings(self, egrid, interpolateWidths=False):
        """
        The ENDF URR tables give us the average resonance parameters, the average resonance spacing
        and the number of degrees of freedom, assuming that the widths are distributed by a chi^2
        probability density function with the given number of degrees of freedom.

        However, later we'll need the level densities.  Below we'll construct them from the
        average resonance spacing for each L, J.

        This function sets several member data as dicts (indexed by L & J) of data and interpolateable functions::

            - levelSpacings: level spacings from ENDF::

                ..math::
                    D_{L,J}(E)

            - averageWidths: average widths from ENDF::

                ..math::
                    \Gamma_{L,J,c}

            - levelSpacingFuncs: level spacings from ENDF, turned into interpolation tables (using XYs.XYs1d instances)
            - levelDensityFuncs: level density as interpolation tables (using XYs.XYs1d instances), derived from level spacings

                ..math::
                    \rho_{L,J}(E)=1/D_{L,J}(E)

            - averageWidthFuncs: average widths from ENDF, turned into interpolation tables (using XYs.XYs1d instances)
            - DOFs: degrees of freedom from ENDF

        :param egrid: the grid to work on
        :param interpolateWidths: flag to determine whether to interpolate the resonance widths
        :return: None
        """
        from numericalFunctions import pointwiseXY_C

        def makeXYs(data,xUnit='eV',xLabel='energy_in',yUnit='b',yLabel="crossSection",dataForm="xys",accuracy=1e-8,
                    interpolation=standardsModule.interpolation.linlinToken):
            theAxes    = axesModule.axes( labelsUnits={1:(xLabel,xUnit), 0:(yLabel,yUnit)} )
            return XYsModule.XYs1d(
                data  = data,
                dataForm = dataForm,
                axes = theAxes,
                interpolation = interpolation,
                accuracy = accuracy
            )

        self.levelSpacings=collections.OrderedDict()
        self.averageWidths=collections.OrderedDict()
        self.levelSpacingFuncs=collections.OrderedDict()
        self.levelDensityFuncs=collections.OrderedDict()
        self.averageWidthFuncs=collections.OrderedDict()
        self.DOFs=collections.OrderedDict()
        for L in self.URR.L_values:
            l = L.L
            for J in L.J_values:
                j = J.J.value

                # dicts for widths and degrees of freedom.
                # widths may be constant or energy-dependent:
                # convert here from PhysicalQuantity to floats:
                self.levelSpacings[(l,j)]=None
                self.averageWidths[(l,j)]={}
                self.levelSpacingFuncs[(l,j)]=None
                self.levelDensityFuncs[(l,j)]=None
                self.averageWidthFuncs[(l,j)]={}
                self.DOFs[(l,j)]={}

                # Set the widths and level spacings
                for wid in ('neutronWidth','captureWidth','fissionWidthA','competitiveWidth','levelSpacing'):

                    # Suck a real column off the energy dependent width table or create a
                    # virtual column using the constant values in the constant width section
                    column = getattr(J.constantWidths, wid, None)
                    if( column is not None ) :
                        column = column.getValueAs('eV') * numpy.ones(len(egrid))
                    elif (bool(J.energyDependentWidths)
                            and J.energyDependentWidths.getColumn( wid, units='eV' )):
                        if interpolateWidths:
                            Nenergies = len(J.energyDependentWidths.getColumn('energy','eV'))
                            interp = pointwiseXY_C.pointwiseXY_C(
                                data = [J.energyDependentWidths.getColumn('energy','eV'), J.energyDependentWidths.getColumn(wid,'eV')],
                                dataForm = "XsAndYs", interpolation = self.URR.interpolation )
                            widthsNow = []
                            for en in egrid:
                                try:
                                    widthsNow.append( interp.evaluate(en) )
                                except Exception as e:
                                    # grrr... data contains invalid log-log or lin-log interpolation
                                    print ("WARNING: unresolved resonance widths contain an invalid interpolation!")
                                    interp2 = pointwiseXY_C.pointwiseXY_C( interp.copyDataToXYs(),
                                            interpolation = standardsModule.interpolation.linlinToken )
                                    widthsNow.append( interp2.evaluate(en) )
                            column = numpy.array( widthsNow )
                        else:
                            column = numpy.array( J.energyDependentWidths.getColumn(wid,'eV') )
                            if len(column) != len(egrid):
                                raise Exception("Inconsistent energy arrays encountered in unresolved region!")

                    # Assign the column data to the right map & set up the interpolated versions
                    if wid == 'levelSpacing':
                        self.levelSpacings[(l,j)]=column
                        self.levelSpacingFuncs[(l,j)]=\
                            makeXYs(
                                data=[ egrid, column ],
                                xLabel="Ex", yLabel="D(Ex)", yUnit="eV", dataForm="xsandys")
                        self.levelDensityFuncs[(l,j)]=\
                            makeXYs(
                                data=[egrid, [1.0/x for x in column]],
                                xLabel="Ex", yLabel="rho(Ex)", yUnit="1/eV",dataForm="xsandys")
                    else:
                        self.averageWidths[(l,j)][wid]=column
                        if type(column) != float and len(column) > 2:
                            self.averageWidthFuncs[(l,j)][wid]=\
                                makeXYs(
                                    data=[egrid, column],
                                    xLabel="Ex", yLabel=wid, yUnit='eV',dataForm="xsandys")

                # Do the degrees of freedom too
                for dof in ('neutronDOF','fissionDOF','competitiveDOF'):
                    self.DOFs[(l,j)][dof] = getattr(J,dof,None)

                # Save the final grid
                self.egrid=egrid

    def rho(self, E):
        """
        The dimensionless parameter rho::

            ..math::
                \rho = k(E) a

        We always calculate channel radius for unresolved region according to the ENDF manual

        :param E: the incident neutron energy
        :return: rho
        """
        a = 0.123 * self.target.getMass('amu')**(1./3.) + 0.08
        return self.k(E) * a

    def getFluctuationIntegrals(self, widths, DOF):
        """
        From subroutine GNRL3 in RECENT. If possible, this will be replaced
        with more basic approach (rather than using lookup table)... not finding
        appropriate equations right now

        Comments from GNRL3 sourcecode::

              Calculate unresolved resonance fluctuation function
              (original coding from AVERAGE4 by Mulki Bhat)
              (new weighting scheme from MC^2-II)

              This routine has been modified to calculate elastic, capture
              and fission fluctuation functions all during one call (as
              opposed to the original version which calculated each reaction
              separately).

              GNX, GGX, GFX and GXX are the widths for elastic, capture,
              fission and competition. MUN, MUF and MUX are the number of
              degrees of freedom for elastic, fission and competition (infinite
              number of degrees assumed for capture). RN, RC and RF are the
              calculated fluctuation integrals for elastic, capture and fission

              The number of degrees of freedom for each distribution (elastic,
              fission or competition) may be 1 to 4. If the number of degrees
              of freedom for any distribution is less than 1 or more than 4
              it will be treated as an infinite number of degrees of freedom
              (which infers that the widths are not distributed, but are rather
              all equal to the average value). This last case is simulated by
              defining an additional 10 point quadrature in which the weight
              for one point is 1.0 and the weight for all other points is zero.
              for the one point of weight 1.0 the average width will be used.

        """
        XX = [[ 3.0013465e-03,1.3219203e-02,1.0004488e-03,1.3219203e-02,1.0e+0],
            [7.8592886e-02,7.2349624e-02,2.6197629e-02,7.2349624e-02,0.0e+0],
            [4.3282415e-01,1.9089473e-01,1.4427472e-01,1.9089473e-01,0.0e+0],
            [1.3345267e+00,3.9528842e-01,4.4484223e-01,3.9528842e-01,0.0e+0],
            [3.0481846e+00,7.4083443e-01,1.0160615e+00,7.4083443e-01,0.0e+0],
            [5.8263198e+00,1.3498293e+00,1.9421066e+00,1.3498293e+00,0.0e+0],
            [9.9452656e+00,2.5297983e+00,3.3150885e+00,2.5297983e+00,0.0e+0],
            [1.5782128e+01,5.2384894e+00,5.2607092e+00,5.2384894e+00,0.0e+0],
            [2.3996824e+01,1.3821772e+01,7.9989414e+00,1.3821772e+01,0.0e+0],
            [3.6216208e+01,7.5647525e+01,1.2072069e+01,7.5647525e+01,0.0e+0],]
        WW = [[1.1120413e-01,3.3773418e-02,3.3376214e-04,1.7623788e-03,1.0e+0],
            [2.3546798e-01,7.9932171e-02,1.8506108e-02,2.1517749e-02,0.0e+0],
            [2.8440987e-01,1.2835937e-01,1.2309946e-01,8.0979849e-02,0.0e+0],
            [2.2419127e-01,1.7652616e-01,2.9918923e-01,1.8797998e-01,0.0e+0],
            [1.0967668e-01,2.1347043e-01,3.3431475e-01,3.0156335e-01,0.0e+0],
            [3.0493789e-02,2.1154965e-01,1.7766657e-01,2.9616091e-01,0.0e+0],
            [4.2930874e-03,1.3365186e-01,4.2695894e-02,1.0775649e-01,0.0e+0],
            [2.5827047e-04,2.2630659e-02,4.0760575e-03,2.5171914e-03,0.0e+0],
            [4.9031965e-06,1.6313638e-05,1.1766115e-04,8.9630388e-10,0.0e+0],
            [1.4079206e-08,0.0000000e+00,5.0989546e-07,0.0000000e+00,0.0e+0],]

        if numpy.all(widths['captureWidth']<=0):
            return 0,0,0
        shape = widths['neutronWidth'].shape
        RN,RC,RF = numpy.zeros(shape), numpy.zeros(shape), numpy.zeros(shape)

        # We may store non-integer DOF, but we just end up converting to int:
        MUN = int( DOF['neutronDOF'] )
        if MUN<1 or MUN>4: MUN=5
        MUF = int( DOF['fissionDOF'] )
        if MUF<1 or MUF>5: MUF=5
        MUX=int( DOF['competitiveDOF'] )
        if MUX<1 or MUX>4: MUX=5
        for j in range(10):
            xj = XX[j][MUN-1]
            wj = WW[j][MUN-1]
            if numpy.any(widths['fissionWidthA']) and numpy.any(widths['competitiveWidth']):
                effj = widths['neutronWidth']*xj+widths['captureWidth']
                for k in range(10):
                    xk = XX[k][MUF-1]
                    wk = WW[k][MUF-1]
                    effjk = effj+widths['fissionWidthA']*xk
                    for i in range(10):
                        xi = XX[i][MUX-1]
                        wi = WW[i][MUX-1]
                        factor = wi*wk*wj*xj/(effjk+widths['competitiveWidth']*xi)
                        RN += xj*factor
                        RC += factor
                        RF += xk*factor
            elif numpy.any(widths['fissionWidthA']):
                effj = widths['neutronWidth']*xj+widths['captureWidth']
                for k in range(10):
                    xk = XX[k][MUF-1]
                    wk = WW[k][MUF-1]
                    factor = wk*wj*xj/(effj+widths['fissionWidthA']*xk)
                    RN += xj*factor
                    RC += factor
                    RF += xk*factor
            elif numpy.any(widths['competitiveWidth']):
                effj = widths['neutronWidth']*xj + widths['captureWidth']
                for k in range(10):
                    xk = XX[k][MUX-1]
                    wk = WW[k][MUX-1]
                    factor = wk*wj*xj/(effj+widths['competitiveWidth']*xk)
                    RN += xj*factor
                    RC += factor
            else:   # only neutron and capture widths:
                factor = wj*xj/(widths['neutronWidth']*xj+widths['captureWidth'])
                RN += xj*factor
                RC += factor
        for arr in (RN,RC,RF):
            arr[ widths['neutronWidth']<=0 ] = 0
        return RN,RC,RF

    def generateEnergyGrid(self, interpolateWidths=False):
        """
        Get the energy grid for reconstructing unresolved resonances. Usually this is just the energy grid
        chosen by the evaluator for storing energy-dependent widths.

        Now, ENDF says to interpolate on the reconstructed average cross section.
        This is stupid (see Red's rant in D.E. Cullen "A Short History of ENDF/B Unresolved Resonance Parameters",
        LLNL Report LLNL-TR-461199, ENDF Report ENDF-369 (2010)).  Better is to interpolate on the model inputs
        (the average widths in the case of URR) and refine the reconstructed cross section to the desired accuracy.
        This is what the interpolateWidths flag controls.

        :param interpolateWidths: if True, interpolate the average widths
        :return: a tuple containing the grid and the interpolate flag
        """
        egrid = set()
        for L in self.URR.L_values:
            for J in L.J_values:
                try: egrid.update( J.energyDependentWidths.getColumn('energy','eV') )
                except: egrid.update( [self.lowerBound, self.upperBound] )
        egrid = sorted( egrid )
        if egrid[0] > self.lowerBound or egrid[-1] < self.upperBound:
            raise ValueError("Energy grid in unresolved region doesn't span stated energy range:" +
                    " (%e - %e) vs (%e - %e)" % (egrid[0], egrid[-1], self.lowerBound, self.upperBound) )
        egrid = numpy.array(egrid)

        # below is a nasty hack since some ENDF files don't supply a dense enough energy grid in the URR.
        # These files should be fixed, but in the meantime add extra points and interpolate the widths:
        energyGridGaps = numpy.argwhere( egrid[1:] / egrid[:-1] > 3 ).flatten()
        if len( energyGridGaps ):
            import math
            if self.verbose:
                print "WARNING: filling large gaps in unresolved energy grid!"
            e_set = set( egrid )
            fixGrid = numpy.array( [1.0, 1.25, 1.5, 1.7, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.2, 8.5] )
            for idx in energyGridGaps:
                lowend, highend = egrid[idx], egrid[idx+1]
                lowPow, highPow = int( math.log10( lowend ) ), int( math.ceil( math.log10( highend ) ) )
                for i in xrange( lowPow, highPow + 1 ):
                    points_to_add = [point for point in 10**i * fixGrid if lowend < point < highend]
                    e_set.update( points_to_add )
            interpolateWidths=True
            egrid = numpy.array( sorted( e_set ) )
        # end of nasty hack

        return egrid, interpolateWidths

    def getCrossSection(self, interpolateWidths=False):
        """
        Get unresolved region cross section for each incident energy in E.
        By default, calculate on the energy grid supplied and then interpolate the resulting cross section.

        If interpolateWidths==True, interpolate the average widths during reconstruction instead.
        """

        # Initialize the energy grid and, if needed, the widths, DOFs and level spacings
        E, interpolateWidths = self.generateEnergyGrid(interpolateWidths=interpolateWidths)
        if self.levelSpacings is None: self.getWidthsAndSpacings( E, interpolateWidths=interpolateWidths )

        # Integrate to get the average cross section, the ENDF way.  Assumes resonances are SLBW ones (ugh)
        captureSum = 0
        elasticSum = 0
        fissionSum = 0
        rho = self.rho(E)
        rhohat = self.URR.scatteringRadius.getValueAs('10*fm') * self.k(E)
        for L in self.URR.L_values:
            l = L.L
            phi = self.phi(l,rhohat)
            for J in L.J_values:
                j = J.J.value
                gfactor = (2.0*abs(j)+1)/(2*(2*self.spin+1))

                # Because the neutron width is really a reduced width in ENDF, we have to convert it to a "regular" width.
                # Save all the widths in a new widths container to simplify coding in the fluctuating integral widget
                VL = self.DOFs[(l,j)]['neutronDOF'] * self.penetrationFactor(l,rho) / rho
                widths = self.averageWidths[(l,j)]
                widths['neutronWidth'] = VL*numpy.sqrt(E)*self.averageWidths[(l,j)]['neutronWidth']

                RN,RC,RF = self.getFluctuationIntegrals(widths,self.DOFs[(l,j)])

                # common factor for all reactions:
                comfac = 2*numpy.pi*gfactor*widths['neutronWidth'] / self.levelSpacings[(l,j)]

                captureSum += RC * widths['captureWidth'] * comfac
                fissionSum += RF * widths['fissionWidthA'] * comfac
                elasticSum += (RN * widths['neutronWidth']-2*numpy.sin(phi)**2) * comfac

            elasticSum += 4*(2*l+1)*numpy.sin(phi)**2

        # common factor 'beta' as row vector:
        beta = numpy.pi / self.k(E)**2
        capture = beta * captureSum
        elastic = beta * elasticSum
        fission = beta * fissionSum
        for reaction in (capture,elastic,fission):
            reaction[ reaction<=0 ] = 0
        total = elastic + capture + fission
        nonelastic = capture + fission

        xscs = {'total':total, 'elastic':elastic, 'capture':capture, 'fission':fission, 'nonelastic':nonelastic}

        # convert to crossSection.pointwise instances, using interpolation specified in the evaluation:
        for key in xscs:
            axes_ = crossSection.defaultAxes()
            xscs[key] = crossSection.XYs1d( axes=axes_, data=zip(E,xscs[key]), interpolation=self.URR.interpolation )
            xscs[key] = xscs[key].domainSlice( self.lowerBound, self.upperBound )

        return xscs

    def sampleRR(self, lastResonanceEnergies, style='goe', verbose=True):
        """
        Generate a sample of a resolved resonant set using the average URR parameters

        :param lastResonanceEnergies: the energy of the last energy from the RRR
        :param verbose: turn on verbose output
        :return: the resonance set as a fudge.core.math.table
        """
        raise NotImplementedError("burr not merged in yet")
        import blurr.level_analysis
        from xData.table import table as gndTable, columnHeader as gndColumnId
        fakeRRR=[]
        # WARNING: be very careful that the columns defined in getFakeResonanceSet match
        #          in both name and order with those defined below
        for lj in lastResonanceEnergies.keys():
            fakeRRR+=blurr.level_analysis.getFakeResonanceSet(
                E0=lastResonanceEnergies[lj],
                style=style,
                L=lj[0], J=lj[1],
                levelDensity=self.levelDensityFuncs[lj],
                aveWidthFuncs=self.averageWidthFuncs[lj],
                DOFs=self.DOFs[lj],
                lowerBound=self.lowerBound,
                upperBound=self.upperBound,
                verbose=verbose)
        result = gndTable( columns = [
                gndColumnId( 0, name="energy", units="eV" ),
                gndColumnId( 1, name="L", units="" ),
                gndColumnId( 2, name="J", units="" ),
                gndColumnId( 3, name="totalWidth", units="eV" ),
                gndColumnId( 4, name="neutronWidth", units="eV" ),
                gndColumnId( 5, name="captureWidth", units="eV" ),
                gndColumnId( 6, name="fissionWidthA", units="eV" ),
                gndColumnId( 6, name="competitiveWidth", units="eV" )],
                data = sorted( fakeRRR, key=lambda(res): res[0]) )   # sort by energy only
        for column in ("totalWidth","fissionWidthA","competitiveWidth"):
            if not any( result.getColumn(column) ):
                result.removeColumn(column)
        return result

    def getURRMoments(self, resClass, nSamples=20, momentPowerList=[1,2,3,4], style='goe', interpolateWidths=True, verbose=True):
        """
        Compute moments of the cross sections

        :param resClass: the class to use to reconstruct the cross section
        :param nSamples: number of realizations to make
        :param momentPowerList:
        :param interpolateWidths: flag to interpolate the widths or not (not==wrong, but not==ENDF way)
        :return:
        """
        import copy

        nMoments = len(momentPowerList)

        # Initialize the widths, DOFs and level spacings
        if self.levelSpacings is None:
            egrid, interpolateWidths = self.generateEnergyGrid(interpolateWidths=interpolateWidths)
            self.getWidthsAndSpacings( egrid, interpolateWidths=interpolateWidths )
        else:
            egrid = self.egrid

        # We'll compute the moments of the cross sections in these arrays (forget correlations between channels for now)
        moments=collections.OrderedDict((
            ('total',      collections.OrderedDict(zip(momentPowerList, copy.copy(nMoments*[0.0])))),
            ('elastic',    collections.OrderedDict(zip(momentPowerList, copy.copy(nMoments*[0.0])))),
            ('capture',    collections.OrderedDict(zip(momentPowerList, copy.copy(nMoments*[0.0])))),
            ('fission',    collections.OrderedDict(zip(momentPowerList, copy.copy(nMoments*[0.0])))),
            ('nonelastic', collections.OrderedDict(zip(momentPowerList, copy.copy(nMoments*[0.0]))))))

        # Get the upper most resonances
        lastResonances={}
        for k in self.levelSpacingFuncs:
            lastResonances[k]=self.getLastResolvedResonanceEnergy(l=k[0],j=k[1])

        fakeResHolder = copy.copy(self.getLastResolvedResonanceRegion())

        # Sample cross section
        for iSample in range( nSamples ):

            # Assign the class that will generate the fake cross sections
            # (we may want to construct this only once and reuse say the energy grid and maybe even consider mixing and matching channels between realizations)
            if True:
                fakeResHolder.resonanceParameters = self.sampleRR(lastResonances,style=style,verbose=verbose)
                fakeResHolder.resonanceParameters.data=self.getLastResolvedResonanceRegion().resonanceParameters.data+fakeResHolder.resonanceParameters.data
                resonanceGenerator = resClass(
                    self.reactionSuite,
                    RR=fakeResHolder,
                    lowerBound=egrid[-2],#self.lowerBound,
                    upperBound=egrid[-1],#self.upperBound,
                    verbose=self.verbose,
                    enableAngDists=False)
#            except AttributeError, err:
#                raise AttributeError( "While attempting to generate URR tables, resonance reconstruction class %s incompatible with data given in %s, got error %s" %
#                                     (resClass.__name__, self.reactionSuite.resonances.resolved.resonances,str(err)))

#            for row in fakeResHolder.resonanceParameters.data:
#                if row[0]>egrid[1] and row[1]<egrid[2]:print row

            # Determine the energy grid to reconstruct on
#            if useFullEGrid:
            tmpEGrid = resonanceGenerator.generateEnergyGrid()
#            else: tmpEGrid=egrid

#            print 'tmpEGrid:',tmpEGrid

            # Compute the cross section for this realization
            # TODO: add in RRR tails from below URR and background R-matrix from above URR
            thisXSs = resonanceGenerator.getCrossSection(tmpEGrid)
            for i,E in enumerate(tmpEGrid):
                print E, thisXSs['elastic'][i]
            exit()

            # Accumulate the moments of the cross sections
            for channel in moments:
                for iMoment in momentPowerList:
                    moments[channel][iMoment]+=pow(thisXSs[channel],iMoment)/nSamples

        return moments

    def getURRPDF(self, resClass, nSamples=20, momentPowerList=[1,2,3,4], interpolateWidths=True, verbose=True):
        moments = self.getURRMoments(resClass, nSamples, momentPowerList, interpolateWidths, verbose)

        # This is where we analyze the accumulated moments to generate the PDF FIXME
        thePDFs = collections.OrderedDict((
            ('total',      None),
            ('elastic',    None),
            ('capture',    None),
            ('fission',    None),
            ('nonelastic', None)))

        return thePDFs

    def getTransmissionCoefficientsFromSumRule(self,skipFission=True):
        """
        Use Moldauer's sum rule to extract the transmission coefficients directly from the URR tables
            P.A. Moldauer Phys. Rev. Lett. 19, 1047-1048 (1967)

        :param skipFission: flag to skip fission, what else?
        :return: a dictionary of results, sorted by channel
        """
        # Initialize the reduced width factors for the elastic channel
        redWidthFactor={}
        for lj in self.averageWidthFuncs:
            if lj[0] not in redWidthFactor:
                redWidthFactor[lj[0]]=XYsModule.XYs1d.createFromFunction(
                    XYsModule.XYs1d.defaultAxes(\
                        labelsUnits={ \
                            XYsModule.yAxisIndex : ( 'gamma' , '' ), \
                            XYsModule.xAxisIndex : ( 'Ex', 'eV' ) }),
                    self.averageWidthFuncs[lj]['neutronWidth'].domain(),
                    lambda E,nope: math.sqrt(E)*self.penetrationFactor( lj[0], self.rho(E) )/self.rho(E),
                    {},
                    1e-6,
                    100)

        # Now compute the Tc's
        Tc={}
        widNames={'capture':'captureWidth','elastic':'neutronWidth','fission':'fissionWidthA'}
        channelClass={'capture':GAMMACHANNEL,'elastic':NEUTRONCHANNEL,'fission':FISSIONCHANNEL}
        for rxn in widNames.keys():
            for lj in self.averageWidthFuncs:
                if rxn=='elastic':
                    eta=math.pi*redWidthFactor[lj[0]]*self.averageWidthFuncs[lj][widNames[rxn]]/self.levelSpacingFuncs[lj] #*self.levelDensityFuncs[lj]
                elif rxn=='fission':
                    if skipFission: continue
                    if widNames[rxn] not in self.averageWidthFuncs[lj]: continue
                    eta=math.pi*self.averageWidthFuncs[lj][widNames[rxn]]/self.levelSpacingFuncs[lj]
                else:
                    eta=math.pi*self.averageWidthFuncs[lj][widNames[rxn]]/self.levelSpacingFuncs[lj] #*self.levelDensityFuncs[lj]
                etasqr=eta*eta
                c=ChannelDesignator(lj[0], lj[1], rxn, len(Tc), int(2.0*abs(lj[0]-lj[1])), gfact=None, particleA=None, particleB=None, isElastic=(rxn=='elastic'), channelClass=channelClass[rxn], useRelativistic=False, eliminated=False)
                Tc[c]=2.0*etasqr*((1.0+1.0/etasqr).applyFunction(lambda x,y:math.sqrt(x),None)-1.0)
        return Tc

RRClassMap={
    fudge.gnd.resonances.SLBW.moniker:{'gnd':fudge.gnd.resonances.SLBW,'proc':SLBWcrossSection},
    fudge.gnd.resonances.MLBW.moniker:{'gnd':fudge.gnd.resonances.MLBW,'proc':MLBWcrossSection},
    fudge.gnd.resonances.RM.moniker:{'gnd':fudge.gnd.resonances.RM,'proc':RMcrossSection},
    fudge.gnd.resonances.RMatrix.moniker:{'gnd':fudge.gnd.resonances.RMatrix,'proc':RMatrixLimitedcrossSection}}
