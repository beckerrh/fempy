# -*- coding: utf-8 -*-
"""
Created on Sun Dec  4 18:14:29 2016

@author: becker
"""

import time
import numpy as np
import scipy.sparse as sparse
try:
    from fempy.meshes.simplexmesh import SimplexMesh
except ModuleNotFoundError:
    from ..meshes.simplexmesh import SimplexMesh


#=================================================================#
class FemP1(object):
    def __init__(self, mesh=None):
        if mesh is not None:
            self.setMesh(mesh)
    def setMesh(self, mesh):
        # assert isinstance(mesh, SimplexMesh)
        self.mesh = mesh
        nloc = self.mesh.dimension+1
        self.locmatmass = np.zeros((nloc, nloc))
        self.locmatlap = np.zeros((nloc, nloc))
        self.nloc = nloc
        ncells, simps = self.mesh.ncells, self.mesh.simplices
        npc = simps.shape[1]
        self.cols = np.tile(simps, npc).flatten()
        self.rows = np.repeat(simps, npc).flatten()
        self.computeFemMatrices()
    def massMatrix(self):
        nnodes = self.mesh.nnodes
        self.massmatrix = sparse.coo_matrix((self.mass, (self.rows, self.cols)), shape=(nnodes, nnodes)).tocsr()
        return self.massmatrix
    def assemble(self, k):
        matxx = np.einsum('nk,nl->nkl', self.cellgrads[:, :, 0], self.cellgrads[:, :, 0])
        matyy = np.einsum('nk,nl->nkl', self.cellgrads[:, :, 1], self.cellgrads[:, :, 1])
        matzz = np.einsum('nk,nl->nkl', self.cellgrads[:, :, 2], self.cellgrads[:, :, 2])
        return ( (matxx+matyy+matzz).T*self.mesh.dV*k).T.flatten()
    def computeFemMatrices(self):
        ncells, normals, cellsOfFaces, facesOfCells, dV = self.mesh.ncells, self.mesh.normals, self.mesh.cellsOfFaces, self.mesh.facesOfCells, self.mesh.dV
        scale = 1/self.mesh.dimension
        self.cellgrads = scale*(normals[facesOfCells].T * self.mesh.sigma.T / dV.T).T
        scalemass = 1 / self.nloc / (self.nloc+1);
        massloc = np.tile(scalemass, (self.nloc,self.nloc))
        massloc.reshape((self.nloc*self.nloc))[::self.nloc+1] *= 2
        self.mass = np.einsum('n,kl->nkl', dV, massloc).flatten()
    def phi(self, ic, x, y, grad):
        return 1./3. + np.dot(grad, np.array([x-self.mesh.centersx[ic], y-self.mesh.centersy[ic]]))
    def elementMassMatrix(self, ic):
        nloc = self.mesh.dimension+1
        scale = self.mesh.dx[ic]/nloc/(nloc+1)
        for ii in range(nloc):
            for jj in range(nloc):
                self.locmatmass[ii,jj] = scale
        for ii in range(nloc):
            self.locmatmass[ii, ii] *= 2
        return self.locmatmass
    def elementLaplaceMatrix(self, ic):
        scale = self.mesh.area[ic]
        grads = self.grad(ic)
        for ii in range(3):
            for jj in range(3):
                self.locmatlap[ii,jj] = np.dot(grads[ii],grads[jj])*scale
        return self.locmatlap
    def grad(self, ic):
        normals = self.mesh.normals[self.mesh.edgesOfCell[ic,:]]
        grads = 0.5*normals/self.mesh.area[ic]
        chsg =  (ic == self.mesh.cellsOfEdge[self.mesh.edgesOfCell[ic,:],0])
        # print("### chsg", chsg, "normals", normals)
        grads[chsg] *= -1.
        return grads
    def testgrad(self):
        for ic in range(fem.mesh.ncells):
            grads = fem.grad(ic)
            for ii in range(3):
                x = self.mesh.x[self.mesh.triangles[ic,ii]]
                y = self.mesh.y[self.mesh.triangles[ic,ii]]
                for jj in range(3):
                    phi = self.phi(ic, x, y, grads[jj])
                    if ii == jj:
                        test = np.abs(phi-1.0)
                        if test > 1e-14:
                            print('ic=', ic, 'grad=', grads)
                            print('x,y', x, y)
                            print('x-xc,y-yc', x-self.mesh.centersx[ic], y-self.mesh.centersy[ic])
                            raise ValueError('wrong in cell={}, ii,jj={},{} test= {}'.format(ic,ii,jj, test))
                    else:
                        test = np.abs(phi)
                        if np.abs(phi) > 1e-14:
                            print('ic=', ic, 'grad=', grads)
                            raise ValueError('wrong in cell={}, ii,jj={},{} test= {}'.format(ic,ii,jj, test))
    def computeErrorL2(self, solex, uh):
        x, y, z = self.mesh.points[:,0], self.mesh.points[:,1], self.mesh.points[:,2]
        e = solex(x, y, z) - uh
        return np.sqrt( np.dot(e, self.massmatrix*e) ), e

# ------------------------------------- #

if __name__ == '__main__':
    trimesh = SimplexMesh(geomname="backwardfacingstep", hmean=0.3)
    fem = FemP1(trimesh)
    fem.testgrad()
    import plotmesh
    import matplotlib.pyplot as plt
    plotmesh.meshWithBoundaries(trimesh)
    plt.show()
