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
Example of how to use the evaluator toolkit to generate a new evaluation in GND.
This includes examples of how to create several different types of cross sections,
distributions and multiplicities including:

    pointwise, lin-lin cross section,
    piecewise cross section with lin-lin and log-log regions,

    angular distribution using Legendre coefficients,
    angular distribution using pointwise data,
    angular distribution using 'mixed' data (ie, Legendre for small incident energy, pointwise at high energy),
    double-differential distribution using the Kalbach-Mann formalism,

    constant multiplicity, and
    pointwise (energy-dependent) multiplicity

The resulting GND file is written out to 'newEvaluation.xml'

Particle masses and excited level energies must be supplied by the evaluator, to ensure that the same values
used during the evaluation are stored in the resulting file. The 'particleLibrary' class helps with this:
it keeps track of all the particles used in the evaluation, and helps to ensure masses are given for each particle.

cmattoon, 1/24/2013
"""

from fudge.evaluationBuilder import *

# Create particle library to keep track of all particles used in the evaluation.
# Once an external particle database is ready, this library could point to that database.
particles = particleLibrary( database=None )

particles.newProduct( 'n', mass='1.0086649157 amu' )   # only need to supply the mass once per particle
particles.newProduct( 'C12', mass='12 amu' )

# initialize the reactionSuite, set units to be used throughout:
rsb = reactionSuiteBuilder( particles, projectile='n', target='C12' )
rsb.setUnits( energy="eV", crossSection="b", mass="amu", time="s" )

# start adding reactions. First elastic:
elastic = reactionBuilder( )
elastic.addCrossSection( crossSectionBuilder( data = zip(
    [ 1e-5, 0.025, 0.1, 1.0, 1000, 1e+6, 1e+7, 2e+7 ],  # incident energies (in units specified above)
    [ 4.73918, 4.73924, 4.73919, 4.739185, 4.734583, 2.5774, 0.65677, 0.98072] # cross section
    ) , form = "Pointwise" ) )

# every product should be created with the particles.newProduct() method. No need to supply the mass a second time:
neutron = particles.newProduct( 'n', multiplicity=1 )
neutron.addDistribution( 'AngularLegendre', data = [
    (1e-05, [1,0,0]),     # (incident energy, [list of Legendre coefficients])
    (1000.0, [1, 1.4011e-4, 0]),
    (1e+6, [1, 0.0648, 9.618e-3, 1.008e-3, -2.7e-4]),
    (1e+7, [1, 0.55, 0.42, 0.33, 0.15, 3e-2, 6e-3]),
    (2e+7, [1, 0.73, 0.52, 0.35, 0.2, 0.113, 4e-2]),
    ] )
elastic.addProduct( neutron )
elastic.addResidual( )  # by default the residual particle distribution is 'recoil'
rsb.addReaction( elastic )


# next reaction: inelastic to 1st excited state
inel = reactionBuilder( )
inel.addCrossSection( crossSectionBuilder( data = zip(
    [4.812e+6, 5e+6, 1e+7, 2e+7],
    [0, 0.2376, 0.3237, 0.0902]
    ) , form = "Pointwise" ) )

neutron = particles.newProduct( 'n', multiplicity=1 )
neutron.addDistribution( 'AngularPointwise', data = [
    (4.812e+6, [(-1, 0.5), (1.0, 0.5)]),  # (incident energy, [pointwise P(mu|E) distribution])
    (5e+6, [(-1.0, 0.015341459), (-0.642788, 0.0116150317), (0.0348995, 0.076536), (0.529919, 0.09379859), (1.0, 3.8338515)]),
    (1e+7, [(-1.0, 0.006829464), (-0.5, 0.006811465), (0.0697565, 0.05496499), (0.529919, 0.0763495), (1.0, 3.960308)]),
    (2e+7, [(-1.0, 6.206978445e-10), (-0.996195, 2.1690096e-09), (0.819152, 0.014544092066), (1.0, 10.89847359)]),
    ] )
inel.addProduct( neutron )

# In this reaction, the residual particle is an excited state. We must at least specify the final level index.
# The excitation energy may be added now or later.
inel.addResidual(  excitationLevel = 1 )
rsb.addReaction( inel )


# inelastic scattering to the continuum (MT91)
inel2 = reactionBuilder( )
inel2.addCrossSection( crossSectionBuilder( data = zip(
    [5.245e+6, 1e+7, 2e+7],
    [0, 0.2867, 0.1023]
    ), form = "Pointwise" ) )

neutron = particles.newProduct( 'n', multiplicity=0 )
neutron.addDistribution( 'Uncorrelated', data = {
    'Angular': ('Isotropic',''),
    'Energy': ('EnergyPointwise',[
        (5.245e+6, [(0,1e+5),(1e-5,0)]),
        (1e+7, [(1e-5,0.348),(1e+0,0.0245),(2e+7,3.457e-4)]),
        (2e+7, [(1e-5,0.1794),(1e+0,0.0423),(2e+7,6.238e-4)]),
        ])
    } )
inel2.addProduct( neutron )

inel2.addResidual( ) #excitationLevel = 'continuum' )
rsb.addReaction( inel2 )


# next reaction (capture)
capture = reactionBuilder( )
captureCrossSection = crossSectionBuilder( data=
# this cross section uses two interpolation regions: log-log and lin-lin.
# The x-values must overlap at the boundary between the two regions:
    (   
        zip(    # region 1 (interpolation rule set below)
            [1e-5, 0.025, 1.0, 1000.0],
            [0.1941545, 0.003884461614102241, 0.0006139706, 2.092767e-05] 
        ), zip( # region 2
            [1000.0, 5000.0, 1e+4, 5e+4, 1e+5, 5e+5, 5e+6, 1e+7, 2e+7],
            [2.0928e-05, 1.2091e-05, 1.0965e-05, 1.3309e-05, 1.705e-05, 2.2e-05, 2.2138e-05, 8.478e-05, 2.17352e-4]
        )
    ) , form="Piecewise" )
captureCrossSection.setInterpolation( 'log', 'log', region=0 ) # use log-log interpolation in the thermal region
capture.addCrossSection( captureCrossSection )

gamma = particles.newProduct( 'gamma' )
gamma.addMultiplicity( zip(
    [1e-5, 0.025, 1.0, 1e+3, 1e+6, 2e+7],
    [0.32, 0.32, 0.3, 0.27, 0.24, 0.22]
    ) )
gamma.addDistribution( 'Isotropic' )
capture.addProduct( gamma )

gamma2 = particles.newProduct( 'gamma' )
gamma2.addMultiplicity( zip(    # energy-dependent multiplicity
    [1e-5, 0.025, 1.0, 1e+3 ,1e+6, 2e+7],
    [0.68, 0.68, 0.7, 0.73, 0.76, 0.78]
    ) )
gamma2.addDistribution( 'Isotropic' )
capture.addProduct( gamma2 )

capture.addResidual( )
rsb.addReaction( capture )


# final reaction: (n,2n)
n2n = reactionBuilder( )
n2n.addCrossSection( crossSectionBuilder( data=zip(
    [20.2958e+6, 2.3e+7, 2.5e+7, 2.7e+7, 3e+7],
    [0.124, 0.678, 1.223, 1.082, 0.642] ), form='Pointwise' ) )

neutron = particles.newProduct( 'n', multiplicity=2 )

# Kalbach-Mann parameters per incident and outgoing energy: (these aren't normalized, just meant for demonstration)
neutron.addDistribution( 'KalbachMann', data= {
    'form': "fr",
    'data': [
        (20.3958e+6, [0, 1.33908e-4, 0, 7467.815, 0, 0]),
        (2.3e+7, [0, 1.550178e-06, 0, 7467.815, 2.821341e-06, 0, 14935.63, 3.772911e-06, 0]),
        (2.5e+7, [0, 4.020352e-7, 2.102763e-3, 7467.815, 7.317085e-7, 2.228161e-3, 14935.63, 9.784961e-7, 2.353558e-3]),
        (2.7e+7, [0, 1.105272e-7, 2.270477e-3, 7467.815, 2.011608e-7, 2.36262e-3, 14935.63, 2.690075e-7, 2.454763e-3]),
        (3e+7, [0, 9.071888e-8, 3.665021e-3, 18669.54, 1.651094e-7, 3.825551e-3, 37339.07, 2.207968e-7, 3.986082e-3, 43227.05, 3.215e-7, 4.1923e-3]),
        ]
    } )
n2n.addProduct( neutron )
n2n.addResidual( )
rsb.addReaction( n2n )


"""
# also add total cross section. Since this channel has no products to identify it, need to supply a name:
total = summedReactionBuilder( name="total" )
total.addCrossSection( crossSectionBuilder( data=zip(
    Elab,     # energies in eV
    totXSec  # xsc in b
    ), form="Pointwise" ) )

rsb.addSummedReaction( total.reaction )
"""


# Some masses and energy levels (for residual products) may still be undefined. Check what masses we still need and add them:
unknownMass, unknownExcitation = particles.checkForUnknownMassOrExcitation( )
if unknownMass: print ( "Particles with undefined mass: " + ' '.join([p.name for p in unknownMass]) )
if unknownExcitation: print ( "Levels with undefined energy: " + ' '.join([p.name for p in unknownExcitation]) )

# fix missing data detected in previous step:
particles.setMass('C11', 11.011433613, 'amu' )
particles.setMass('C13', 13.00335483778, 'amu' )

particles.setExcitationEnergy( 'C12_e1', 4438.91, 'keV' )

# Once all reactions are added, use the finalize() method.
# This does some checking and fixing, and returns a reactionSuite instance.
reactionSuite = rsb.finalize()
reactionSuite.saveToFile( "newEvaluation.xml" )

