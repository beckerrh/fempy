import sys
from os import path
simfempypath = path.dirname(path.dirname(path.dirname(path.abspath(__file__))))
sys.path.append(simfempypath)

import simfempy.meshes.testmeshes as testmeshes
from simfempy.applications.stokes import Stokes
import simfempy.applications.problemdata
from simfempy.test.test_analytic import test_analytic

#----------------------------------------------------------------#
def test(dim, **kwargs):
    exactsolution = kwargs.pop('exactsolution', 'Linear')
    data = simfempy.applications.problemdata.ProblemData()
    data.params.scal_glob['mu'] = kwargs.pop('mu', 1)
    paramargs = {}
    if dim==2:
        data.ncomp=2
        createMesh = testmeshes.unitsquare
        colordir = [1000,1001,1003]
        colorneu = [1002]
        # colordir = [1000,1002,1001,1003]
        # colorneu = []
    else:
        data.ncomp=3
        createMesh = testmeshes.unitcube
        raise NotImplementedError("no")
    data.bdrycond.set("Dirichlet", colordir)
    data.bdrycond.set("Neumann", colorneu)
    data.postproc.set(name='bdrypmean', type='bdry_pmean', colors=colorneu)
    data.postproc.set(name='bdrynflux', type='bdry_nflux', colors=colordir)
    linearsolver = kwargs.pop('linearsolver', 'umf')
    applicationargs= {'problemdata': data, 'exactsolution': exactsolution, 'linearsolver': linearsolver}
    paramargs['dirichletmethod'] = kwargs.pop('dirichletmethod', ['strong','nitshe'])
    return test_analytic(application=Stokes, createMesh=createMesh, paramargs=paramargs, applicationargs=applicationargs, **kwargs)



#================================================================#
if __name__ == '__main__':
    # test(dim=2, exactsolution=[["x**2-y","-2*x*y+x**2"],"x*y"], niter=8, plotsolution=False, linearsolver='gmres')
    test(dim=2, exactsolution=[["-y","x"],"10"], niter=3, plotsolution=False, linearsolver='gmres')
    # test(dim=2, exactsolution=[["0","1"],"1"], niter=2, h1=2)
