# -*- coding: utf-8 -*-
"""
Created on Sun Dec  4 18:14:29 2016

@author: becker
"""

import numpy as np
import scipy.linalg as linalg
import scipy.sparse as sparse
try:
    from simfempy.meshes.simplexmesh import SimplexMesh
except ModuleNotFoundError:
    from ..meshes.simplexmesh import SimplexMesh
import simfempy.fems.bdrydata


#=================================================================#
class FemP1(object):
    def __init__(self, mesh=None):
        if mesh is not None:
            self.setMesh(mesh)
        self.dirichlet_al = 10

    def setMesh(self, mesh, bdrycond=None):
        self.mesh = mesh
        self.nloc = self.mesh.dimension+1
        simps = self.mesh.simplices
        self.cols = np.tile(simps, self.nloc).reshape(-1)
        self.rows = np.repeat(simps, self.nloc).reshape(-1)
        self.computeCellGrads()
        self.massmatrix = self.computeMassMatrix()
        if bdrycond:
            self.robinmassmatrix = self.computeBdryMassMatrix(bdrycond, type="Robin")

    def computeCellGrads(self):
        ncells, normals, cellsOfFaces, facesOfCells, dV = self.mesh.ncells, self.mesh.normals, self.mesh.cellsOfFaces, self.mesh.facesOfCells, self.mesh.dV
        scale = -1/self.mesh.dimension
        # print("dV", np.where(dV<0.0001))
        # print("dV", dV[dV<0.00001])
        self.cellgrads = scale*(normals[facesOfCells].T * self.mesh.sigma.T / dV.T).T

    def computeMassMatrix(self, lumped=False):
        nnodes = self.mesh.nnodes
        scalemass = 1 / self.nloc / (self.nloc+1);
        massloc = np.tile(scalemass, (self.nloc,self.nloc))
        massloc.reshape((self.nloc*self.nloc))[::self.nloc+1] *= 2
        mass = np.einsum('n,kl->nkl', self.mesh.dV, massloc).flatten()
        return sparse.coo_matrix((mass, (self.rows, self.cols)), shape=(nnodes, nnodes)).tocsr()

    def computeBdryMassMatrix(self, bdrycond, type, lumped=False):
        nnodes = self.mesh.nnodes
        rows = np.empty(shape=(0), dtype=int)
        cols = np.empty(shape=(0), dtype=int)
        mat = np.empty(shape=(0), dtype=float)
        if lumped:
            for color, faces in self.mesh.bdrylabels.items():
                if bdrycond.type[color] != type: continue
                scalemass = bdrycond.param[color]/ self.mesh.dimension
                normalsS = self.mesh.normals[faces]
                dS = linalg.norm(normalsS, axis=1)
                nodes = self.mesh.faces[faces]
                rows = np.append(rows, nodes)
                cols = np.append(cols, nodes)
                mass = np.repeat(scalemass*dS,self.mesh.dimension)
                mat = np.append(mat, mass)
            return sparse.coo_matrix((mat, (rows, cols)), shape=(nnodes, nnodes)).tocsr()
        else:
            for color, faces in self.mesh.bdrylabels.items():
                if bdrycond.type[color] != type: continue
                scalemass = bdrycond.param[color] / (1+self.mesh.dimension)/self.mesh.dimension
                normalsS = self.mesh.normals[faces]
                dS = linalg.norm(normalsS, axis=1)
                nodes = self.mesh.faces[faces]
                nloc = self.nloc-1
                rows = np.append(rows, np.repeat(nodes, nloc).reshape(-1))
                cols = np.append(cols, np.tile(nodes, nloc).reshape(-1))
                massloc = np.tile(scalemass, (nloc, nloc))
                massloc.reshape((nloc*nloc))[::nloc+1] *= 2
                mat = np.append(mat, np.einsum('n,kl->nkl', dS, massloc).reshape(-1))
            return sparse.coo_matrix((mat, (rows, cols)), shape=(nnodes, nnodes)).tocsr()

    def prepareBoundary(self, colorsdir, postproc):
        bdrydata = simfempy.fems.bdrydata.BdryData()
        bdrydata.nodesdir={}
        bdrydata.nodedirall = np.empty(shape=(0), dtype=int)
        for color in colorsdir:
            facesdir = self.mesh.bdrylabels[color]
            bdrydata.nodesdir[color] = np.unique(self.mesh.faces[facesdir].flat[:])
            bdrydata.nodedirall = np.unique(np.union1d(bdrydata.nodedirall, bdrydata.nodesdir[color]))
        bdrydata.nodesinner = np.setdiff1d(np.arange(self.mesh.nnodes, dtype=int),bdrydata.nodedirall)
        bdrydata.nodesdirflux={}
        if not postproc: return bdrydata
        for key, val in postproc.items():
            type,data = val.split(":")
            if type != "bdrydn": continue
            colors = [int(x) for x in data.split(',')]
            bdrydata.nodesdirflux[key] = np.empty(shape=(0), dtype=int)
            for color in colors:
                facesdir = self.mesh.bdrylabels[color]
                bdrydata.nodesdirflux[key] = np.unique(np.union1d(bdrydata.nodesdirflux[key], np.unique(self.mesh.faces[facesdir].flatten())))
        return bdrydata

    def matrixDiffusion(self, k, bdrycond, method, bdrydata):
        nnodes = self.mesh.nnodes
        matxx = np.einsum('nk,nl->nkl', self.cellgrads[:, :, 0], self.cellgrads[:, :, 0])
        matyy = np.einsum('nk,nl->nkl', self.cellgrads[:, :, 1], self.cellgrads[:, :, 1])
        matzz = np.einsum('nk,nl->nkl', self.cellgrads[:, :, 2], self.cellgrads[:, :, 2])
        mat = ( (matxx+matyy+matzz).T*self.mesh.dV*k).T.flatten()
        A = sparse.coo_matrix((mat, (self.rows, self.cols)), shape=(nnodes, nnodes)).tocsr()
        A += self.robinmassmatrix
        return self.matrixDirichlet(A, bdrycond, method, bdrydata)

    def computeRhs(self, u, rhs, kheatcell, bdrycond, method, bdrydata):
        b = np.zeros(self.mesh.nnodes)
        if rhs:
            x, y, z = self.mesh.points.T
            b += self.massmatrix * rhs(x, y, z)

        help = np.zeros(self.mesh.nnodes)
        for color, faces in self.mesh.bdrylabels.items():
            if bdrycond.type[color] != "Robin": continue
            nodes = np.unique(self.mesh.faces[faces].reshape(-1))
            x, y, z = self.mesh.points[nodes].T
            help[nodes] = bdrycond.fct[color](x, y, z)
        b += self.robinmassmatrix*help

        normals =  self.mesh.normals
        scale = 1 / self.mesh.dimension
        for color, faces in self.mesh.bdrylabels.items():
            if bdrycond.type[color] != "Neumann": continue
            normalsS = normals[faces]
            dS = linalg.norm(normalsS,axis=1)
            normalsS = normalsS/dS[:,np.newaxis]
            assert(dS.shape[0] == len(faces))
            x1, y1, z1 = self.mesh.pointsf[faces].T
            nx, ny, nz = normalsS.T
            bS = scale * bdrycond.fct[color](x1, y1, z1, nx, ny, nz) * dS
            np.add.at(b, self.mesh.faces[faces].T, bS)
        if bdrycond.hasExactSolution():
            for color, faces in self.mesh.bdrylabels.items():
                if bdrycond.type[color] != "Robin": continue
                normalsS = normals[faces]
                dS = linalg.norm(normalsS, axis=1)
                normalsS = normalsS / dS[:, np.newaxis]
                assert (dS.shape[0] == len(faces))
                x1, y1, z1 = self.mesh.pointsf[faces].T
                nx, ny, nz = normalsS.T
                bS = scale * bdrycond.fctexact["Neumann"](x1, y1, z1, nx, ny, nz) * dS
                np.add.at(b, self.mesh.faces[faces].T, bS)
        return self.vectorDirichlet(b, u, bdrycond, method, bdrydata)

    def matrixDirichlet(self, A, bdrycond, method, bdrydata):
        nodesdir, nodedirall, nodesinner, nodesdirflux = bdrydata.nodesdir, bdrydata.nodedirall, bdrydata.nodesinner, bdrydata.nodesdirflux
        nnodes = self.mesh.nnodes
        for key, nodes in nodesdirflux.items():
            nb = nodes.shape[0]
            help = sparse.dok_matrix((nb, nnodes))
            for i in range(nb): help[i, nodes[i]] = 1
            bdrydata.Asaved[key] = help.dot(A)
        bdrydata.A_inner_dir = A[nodesinner, :][:, nodedirall]
        if method == 'trad':
            help = np.ones((nnodes))
            help[nodedirall] = 0
            help = sparse.dia_matrix((help, 0), shape=(nnodes, nnodes))
            A = help.dot(A.dot(help))
            help = np.zeros((nnodes))
            help[nodedirall] = 1.0
            help = sparse.dia_matrix((help, 0), shape=(nnodes, nnodes))
            A += help
        else:
            bdrydata.A_dir_dir = self.dirichlet_al*A[nodedirall, :][:, nodedirall]
            help = np.ones(nnodes)
            help[nodedirall] = 0
            help = sparse.dia_matrix((help, 0), shape=(nnodes, nnodes))
            help2 = np.zeros(nnodes)
            help2[nodedirall] = np.sqrt(self.dirichlet_al)
            help2 = sparse.dia_matrix((help2, 0), shape=(nnodes, nnodes))
            A = help.dot(A.dot(help)) + help2.dot(A.dot(help2))
        return A, bdrydata

    def vectorDirichlet(self, b, u, bdrycond, method, bdrydata):
        nodesdir, nodedirall, nodesinner, nodesdirflux = bdrydata.nodesdir, bdrydata.nodedirall, bdrydata.nodesinner, bdrydata.nodesdirflux
        if u is None: u = np.zeros_like(b)
        else: assert u.shape == b.shape
        x, y, z = self.mesh.points.T
        for key, nodes in nodesdirflux.items():
            bdrydata.bsaved[key] = b[nodes]
        if method == 'trad':
            for color, nodes in nodesdir.items():
                dirichlet = bdrycond.fct[color](x[nodes], y[nodes], z[nodes])
                # print("dirichlet.shape",dirichlet.shape)
                # print("dirichlet",dirichlet)
                # print("b[nodes]",b[nodes])
                b[nodes] = dirichlet
                u[nodes] = b[nodes]
            b[nodesinner] -= bdrydata.A_inner_dir * b[nodedirall]
        else:
            for color, nodes in nodesdir.items():
                dirichlet = bdrycond.fct[color]
                u[nodes] = dirichlet(x[nodes], y[nodes], z[nodes])
                b[nodes] = 0
            b[nodesinner] -= bdrydata.A_inner_dir * u[nodedirall]
            b[nodedirall] += bdrydata.A_dir_dir * u[nodedirall]
        return b, u, bdrydata

    def boundaryvec(self, b, u, bdrycond, method, bdrydata):
        nodesdir, nodedirall, nodesinner, nodesdirflux = bdrydata.nodesdir, bdrydata.nodedirall, bdrydata.nodesinner, bdrydata.nodesdirflux
        Asaved, A_inner_dir, A_dir_dir = bdrydata.Asaved, bdrydata.A_inner_dir, bdrydata.A_dir_dir
        x, y, z = self.mesh.points.T
        for key, nodes in nodesdirflux.items():
            bdrydata.bsaved[key] = b[nodes]
        if method == 'trad':
            for color, nodes in nodesdir.items():
                dirichlet = bdrycond.fct[color]
                if dirichlet:
                    b[nodes] = dirichlet(x[nodes], y[nodes], z[nodes])
                else:
                    b[nodes] = 0
                u[nodes] = b[nodes]
            b[nodesinner] -= A_inner_dir * u[nodedirall]
        else:
            for color, nodes in nodesdir.items():
                dirichlet = bdrycond.fct[color]
                if dirichlet:
                    u[nodes] = dirichlet(x[nodes], y[nodes], z[nodes])
                else:
                    u[nodes] = 0
                b[nodes] = 0
            b[nodesinner] -= A_inner_dir * u[nodedirall]
            b[nodedirall] += A_dir_dir * u[nodedirall]
        return b, u, bdrydata

    def tonode(self, u):
        return u

    def grad(self, ic):
        normals = self.mesh.normals[self.mesh.facesOfCells[ic,:]]
        grads = 0.5*normals/self.mesh.dV[ic]
        chsg =  (ic == self.mesh.cellsOfFaces[self.mesh.facesOfCells[ic,:],0])
        # print("### chsg", chsg, "normals", normals)
        grads[chsg] *= -1.
        return grads

    def computeErrorL2(self, solexact, uh):
        x, y, z = self.mesh.points.T
        en = solexact(x, y, z) - uh
        xc, yc, zc = self.mesh.pointsc.T
        ec = solexact(xc, yc, zc) - np.mean(uh[self.mesh.simplices], axis=1)
        return np.sqrt( np.dot(en, self.massmatrix*en) ), np.sqrt(np.sum(ec**2* self.mesh.dV)), en

    def computeErrorFluxL2(self, solexact, diffcell, uh):
        xc, yc, zc = self.mesh.pointsc.T
        graduh = np.einsum('nij,ni->nj', self.cellgrads, uh[self.mesh.simplices])
        errv = 0
        for i in range(self.mesh.dimension):
            solxi = solexact.d(i, xc, yc, zc)
            errv += np.sum( diffcell*(solxi-graduh[:,i])**2* self.mesh.dV)
        return np.sqrt(errv)


    def computeBdryMean(self, u, key, data):
        colors = [int(x) for x in data.split(',')]
        mean, omega = 0, 0
        for color in colors:
            faces = self.mesh.bdrylabels[color]
            normalsS = self.mesh.normals[faces]
            dS = linalg.norm(normalsS, axis=1)
            omega += np.sum(dS)
            mean += np.sum(dS*np.mean(u[self.mesh.faces[faces]],axis=1))
        return mean/omega

    def computeBdryDn(self, u, key, data, bsaved, Asaved):
        # colors = [int(x) for x in data.split(',')]
        # omega = 0
        # for color in colors:
        #     omega += np.sum(linalg.norm(self.mesh.normals[self.mesh.bdrylabels[color]],axis=1))
        flux = np.sum(Asaved*u - bsaved)
        return flux

    def computeBdryFct(self, u, key, data):
        colors = [int(x) for x in data.split(',')]
        nodes = np.empty(shape=(0), dtype=int)
        for color in colors:
            faces = self.mesh.bdrylabels[color]
            nodes = np.unique(np.union1d(nodes, self.mesh.faces[faces].ravel()))
        return self.mesh.points[nodes], u[nodes]

    def computePointValues(self, u, key, data):
        colors = [int(x) for x in data.split(',')]
        up = np.empty(len(colors))
        for i,color in enumerate(colors):
            nodes = self.mesh.vertices[self.mesh.vertex_labels==color]
            up[i] = u[nodes]
        return up
# ------------------------------------- #

if __name__ == '__main__':
    trimesh = SimplexMesh(geomname="backwardfacingstep", hmean=0.3)
    fem = FemP1(trimesh)
    fem.testgrad()
    import plotmesh
    import matplotlib.pyplot as plt
    plotmesh.meshWithBoundaries(trimesh)
    plt.show()
