# -*- coding: utf-8 -*-
"""
Created on Sun Dec  4 18:14:29 2016

@author: becker
"""

import numpy as np
import scipy.sparse as sparse
try:
    from fempy.meshes.trianglemesh import TriangleMesh
except ModuleNotFoundError:
    from ..meshes.trianglemesh import TriangleMesh


#=================================================================#
class FemP12D(object):
    def __init__(self, mesh=None):
        if mesh is not None:
            self.setMesh(mesh)
        self.locmatmass = np.zeros((3,3))
        self.locmatlap = np.zeros((3,3))
    def setMesh(self, mesh):
        assert isinstance(mesh, TriangleMesh)
        self.mesh = mesh
        ncells, x, y, simps = self.mesh.ncells, self.mesh.x, self.mesh.y, self.mesh.triangles
        self.rows = np.array([np.outer(simps[s],np.ones(3, dtype=int)) for s in range(ncells)]).flatten()
        self.cols = np.array([np.outer(np.ones(3, dtype=int),simps[s]) for s in range(ncells)]).flatten()

        S = np.array(((-1,-1),(1,0),(0,1)))
        A1 = np.dot(x[simps], S)
        A2 = np.dot(y[simps], S)
        self.Adet = A1[:, 0] * A2[:, 1] - A1[:, 1] * A2[:, 0]
        # print('self.Adet.shape', self.Adet.shape)
        # print('A1.shape', A1.shape)

        # Coefficients of inverse mapping
        Ap1 = np.c_[A2[:, 1], -A1[:, 1]] / self.Adet.reshape(ncells, 1)
        Ap2 = np.c_[-A2[:, 0], A1[:, 0]] / self.Adet.reshape(ncells, 1)

        # print('Ap1.shape', Ap1.shape)

        # Basic matrix types on the reference element
        self.M = np.array(((2, 1, 1), (1, 2, 1), (1, 1, 2))) / 24.0
        self.Kxx = np.array(((1, -1, 0), (-1, 1, 0), (0, 0, 0))) / 2.0
        self.Kxy = np.array(((1, 0, -1), (-1, 0, 1), (0, 0, 0))) / 2.0
        self.Kyy = np.array(((1, 0, -1), (0, 0, 0), (-1, 0, 1))) / 2.0
        self.Phi1 = np.array(((6, 2, 2), (2, 2, 1), (2, 1, 2))) / 120.0
        self.Phi2 = np.array(((2, 2, 1), (2, 6, 2), (1, 2, 2))) / 120.0
        self.Phi3 = np.array(((2, 1, 2), (1, 2, 2), (2, 2, 6))) / 120.0

        # Compute all of the elemental stiffness and mass matrices
        self.cxx = (Ap1[:, 0] ** 2 + Ap1[:, 1] ** 2) * self.Adet
        self.cxy = (Ap1[:, 0] * Ap2[:, 0] + Ap1[:, 1] * Ap2[:, 1]) * self.Adet
        self.cyy = (Ap2[:, 0] ** 2 + Ap2[:, 1] ** 2) * self.Adet

        # print('self.cxx.shape', self.cxx.shape)

    def assemble(self, k):
        Kel= \
        np.kron(k * self.cxx, self.Kxx) + \
        np.kron(k * self.cxy, self.Kxy) + \
        np.kron(k * self.cxy, self.Kxy.T) + \
        np.kron(k * self.cyy, self.Kyy)
        return Kel.flatten("F")

    def phi(self, ic, x, y, grad):
        return 1./3. + np.dot(grad, np.array([x-self.mesh.centersx[ic], y-self.mesh.centersy[ic]]))
    def elementMassMatrix(self, ic):
        scale = self.mesh.area[ic]/12
        for ii in range(3):
            for jj in range(3):
                self.locmatmass[ii,jj] = scale
        for ii in range(3):
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

    def massMatrix(self):
        nnodes, ncells = self.mesh.nnodes, self.mesh.ncells
        x, y, simps, xc, yc = self.mesh.x, self.mesh.y, self.mesh.triangles, self.mesh.centersx, self.mesh.centersy
        nlocal = 9
        index = np.zeros(nlocal*ncells, dtype=int)
        jndex = np.zeros(nlocal*ncells, dtype=int)
        A = np.zeros(nlocal*ncells, dtype=np.float64)
        count = 0
        for ic in range(ncells):
            mass = self.elementMassMatrix(ic)
            for ii in range(3):
                for jj in range(3):
                    index[count+3*ii+jj] = simps[ic, ii]
                    jndex[count+3*ii+jj] = simps[ic, jj]
                    A[count + 3 * ii + jj] += mass[ii,jj]
            count += nlocal
        return sparse.coo_matrix((A, (index, jndex)), shape=(nnodes, nnodes)).tocsr()


# ------------------------------------- #

if __name__ == '__main__':
    trimesh = TriangleMesh(geomname="backwardfacingstep", hmean=0.3)
    fem = FemP12D(trimesh)
    fem.testgrad()
    import plotmesh
    import matplotlib.pyplot as plt
    plotmesh.meshWithBoundaries(trimesh)
    plt.show()
