# -*- coding: utf-8 -*-
"""
Created on Sun Dec  4 18:14:29 2016

@author: becker
"""

import numpy as np
import scipy.linalg as linalg
import scipy.sparse as sparse
import simfempy.fems.bdrydata
import simfempy.tools.barycentric
from simfempy.fems import fem


#=================================================================#
class CR1(fem.Fem):
    def __init__(self, mesh=None):
        super().__init__(mesh)
        self.dirichlet_al = 10
    def setMesh(self, mesh):
        super().setMesh(mesh)
        self.nloc = self.mesh.dimension+1
        self.cols = np.tile(self.mesh.facesOfCells, self.nloc).ravel()
        self.rows = np.repeat(self.mesh.facesOfCells, self.nloc).ravel()
        self.cellgrads = self.computeCellGrads()
    def nunknowns(self): return self.mesh.nfaces
    def computeCellGrads(self):
        ncells, normals, cellsOfFaces, facesOfCells, dV = self.mesh.ncells, self.mesh.normals, self.mesh.cellsOfFaces, self.mesh.facesOfCells, self.mesh.dV
        return (normals[facesOfCells].T * self.mesh.sigma.T / dV.T).T
    def computeMassMatrix(self, coeff=1):
        ncells, normals, cellsOfFaces, facesOfCells, dV = self.mesh.ncells, self.mesh.normals, self.mesh.cellsOfFaces, self.mesh.facesOfCells, self.mesh.dV
        dim = self.mesh.dimension
        scalemass = (2-dim) / (dim+1) / (dim+2)
        massloc = np.tile(scalemass, (self.nloc,self.nloc))
        massloc.reshape((self.nloc*self.nloc))[::self.nloc+1] = (2-dim + dim*dim) / (dim+1) / (dim+2)
        mass = np.einsum('n,kl->nkl', dV, massloc).ravel()
        nfaces = self.mesh.nfaces
        return sparse.coo_matrix((mass, (self.rows, self.cols)), shape=(nfaces, nfaces)).tocsr()
    def computematrixDiffusion(self, coeff):
        nfaces = self.mesh.nfaces
        matxx = np.einsum('nk,nl->nkl', self.cellgrads[:, :, 0], self.cellgrads[:, :, 0])
        matyy = np.einsum('nk,nl->nkl', self.cellgrads[:, :, 1], self.cellgrads[:, :, 1])
        matzz = np.einsum('nk,nl->nkl', self.cellgrads[:, :, 2], self.cellgrads[:, :, 2])
        mat = ( (matxx+matyy+matzz).T*self.mesh.dV*coeff).T.ravel()
        return sparse.coo_matrix((mat, (self.rows, self.cols)), shape=(nfaces, nfaces)).tocsr()
    def computeBdryMassMatrix(self, colors=None, coeff=1, lumped=False):
        nfaces = self.mesh.nfaces
        rows = np.empty(shape=(0), dtype=int)
        cols = np.empty(shape=(0), dtype=int)
        mat = np.empty(shape=(0), dtype=float)
        for color in colors:
            faces = self.mesh.bdrylabels[color]
            normalsS = self.mesh.normals[faces]
            if isinstance(coeff, dict):
                scalemass = coeff[color]
                dS = linalg.norm(normalsS, axis=1)
            else:
                scalemass = 1
                dS = linalg.norm(normalsS, axis=1)*coeff[faces]
            cols = np.append(cols, faces)
            rows = np.append(rows, faces)
            mat = np.append(mat, scalemass*dS)
        return sparse.coo_matrix((mat, (rows, cols)), shape=(nfaces, nfaces)).tocsr()
    def prepareBoundary(self, colorsdir, colorsflux=[]):
        bdrydata = simfempy.fems.bdrydata.BdryData()
        bdrydata.facesdirall = np.empty(shape=(0), dtype=np.uint)
        bdrydata.colorsdir = colorsdir
        for color in colorsdir:
            facesdir = self.mesh.bdrylabels[color]
            bdrydata.facesdirall = np.unique(np.union1d(bdrydata.facesdirall, facesdir))
        bdrydata.facesinner = np.setdiff1d(np.arange(self.mesh.nfaces, dtype=int), bdrydata.facesdirall)
        bdrydata.facesdirflux = {}
        for color in colorsflux:
            facesdir = self.mesh.bdrylabels[color]
            bdrydata.facesdirflux[color] = facesdir
        return bdrydata
    def vectorBoundary(self, b, u, bdrycond, method, bdrydata):
        facesdirflux, facesinner, facesdirall, colorsdir = bdrydata.facesdirflux, bdrydata.facesinner, bdrydata.facesdirall, bdrydata.colorsdir
        x, y, z = self.mesh.pointsf.T
        if u is None: u = np.zeros_like(b)
        else: assert u.shape == b.shape
        for color, faces in facesdirflux.items():
            bdrydata.bsaved[color] = b[faces]
        if method == 'trad':
            for color in colorsdir:
                faces = self.mesh.bdrylabels[color]
                dirichlet = bdrycond.fct[color]
                if color in bdrycond.fct:
                    b[faces] = dirichlet(x[faces], y[faces], z[faces])
                else:
                    b[faces] = 0
                u[faces] = b[faces]
            b[facesinner] -= bdrydata.A_inner_dir * b[facesdirall]
        else:
            for color in colorsdir:
                faces = self.mesh.bdrylabels[color]
                dirichlet = bdrycond.fct[color]
                if dirichlet:
                    u[faces] = dirichlet(x[faces], y[faces], z[faces])
                else:
                    u[faces] = 0
                b[faces] = 0
            b[facesinner] -= bdrydata.A_inner_dir * u[facesdirall]
            b[facesdirall] += bdrydata.A_dir_dir * u[facesdirall]
        return b, u, bdrydata
    def vectorBoundaryZero(self, du, bdrydata):
        facesdirflux, facesinner, facesdirall, colorsdir = bdrydata.facesdirflux, bdrydata.facesinner, bdrydata.facesdirall, bdrydata.colorsdir
        du[facesdirall] = 0
        return du
    def matrixBoundary(self, A, method, bdrydata):
        facesdirflux, facesinner, facesdirall, colorsdir = bdrydata.facesdirflux, bdrydata.facesinner, bdrydata.facesdirall, bdrydata.colorsdir
        nfaces = self.mesh.nfaces
        for color, faces in facesdirflux.items():
            nb = faces.shape[0]
            help = sparse.dok_matrix((nb, nfaces))
            for i in range(nb): help[i, faces[i]] = 1
            bdrydata.Asaved[color] = help.dot(A)
        bdrydata.A_inner_dir = A[facesinner, :][:, facesdirall]
        if method == 'trad':
            help = np.ones((nfaces))
            help[facesdirall] = 0
            help = sparse.dia_matrix((help, 0), shape=(nfaces, nfaces))
            A = help.dot(A.dot(help))
            help = np.zeros((nfaces))
            help[facesdirall] = 1.0
            help = sparse.dia_matrix((help, 0), shape=(nfaces, nfaces))
            A += help
        else:
            bdrydata.A_dir_dir = self.dirichlet_al*A[facesdirall, :][:, facesdirall]
            help = np.ones((nfaces))
            help[facesdirall] = 0
            help = sparse.dia_matrix((help, 0), shape=(nfaces, nfaces))
            help2 = np.zeros((nfaces))
            help2[facesdirall] = np.sqrt(self.dirichlet_al)
            help2 = sparse.dia_matrix((help2, 0), shape=(nfaces, nfaces))
            A = help.dot(A.dot(help)) + help2.dot(A.dot(help2))
        return A, bdrydata
    def tonode(self, u):
        unodes = np.zeros(self.mesh.nnodes)
        scale = self.mesh.dimension
        np.add.at(unodes, self.mesh.simplices.T, np.sum(u[self.mesh.facesOfCells], axis=1))
        np.add.at(unodes, self.mesh.simplices.T, -scale*u[self.mesh.facesOfCells].T)
        countnodes = np.zeros(self.mesh.nnodes, dtype=int)
        np.add.at(countnodes, self.mesh.simplices.T, 1)
        unodes /= countnodes
        return unodes
    def computeErrorL2Cell(self, solexact, uh):
        xc, yc, zc = self.mesh.pointsc.T
        ec = solexact(xc, yc, zc) - np.mean(uh[self.mesh.facesOfCells], axis=1)
        return np.sqrt(np.sum(ec**2* self.mesh.dV)), ec
    def computeErrorL2Node(self, solexact, uh):
        x, y, z = self.mesh.pointsf.T
        en = solexact(x, y, z) - uh
        Men = np.zeros_like(en)
        return np.sqrt( np.dot(en, self.massDot(Men,en)) ), en
    def computeErrorFluxL2(self, solexact, diffcell, uh):
        xc, yc, zc = self.mesh.pointsc.T
        graduh = np.einsum('nij,ni->nj', self.cellgrads, uh[self.mesh.facesOfCells])
        errv = 0
        for i in range(self.mesh.dimension):
            solxi = solexact.d(i, xc, yc, zc)
            errv += np.sum( diffcell*(solxi-graduh[:,i])**2* self.mesh.dV)
        return np.sqrt(errv)
    def computeBdryMean(self, u, colors):
        mean, omega = np.zeros(len(colors)), np.zeros(len(colors))
        for i,color in enumerate(colors):
            faces = self.mesh.bdrylabels[color]
            normalsS = self.mesh.normals[faces]
            dS = linalg.norm(normalsS, axis=1)
            omega[i] = np.sum(dS)
            mean[i] = np.sum(dS*u[faces])
        return mean/omega
    def comuteFluxOnRobin(self, u, faces, dS, uR, cR):
        uhmean =  np.sum(dS * u[faces])
        xf, yf, zf = self.mesh.pointsf[faces].T
        nx, ny, nz = np.mean(self.mesh.normals[faces], axis=0)
        if uR:
            try:
                uRmean =  np.sum(dS * uR(xf, yf, zf, nx, ny, nz))
            except:
                uRmean =  np.sum(dS * uR(xf, yf, zf))
        else: uRmean=0
        return cR*(uRmean-uhmean)
    def computeBdryNormalFlux(self, u, colors, bdrydata, bdrycond):
        flux, omega = np.zeros(len(colors)), np.zeros(len(colors))
        for i,color in enumerate(colors):
            faces = self.mesh.bdrylabels[color]
            normalsS = self.mesh.normals[faces]
            dS = linalg.norm(normalsS, axis=1)
            omega[i] = np.sum(dS)
            if color in bdrydata.bsaved.keys():
                bs, As = bdrydata.bsaved[color], bdrydata.Asaved[color]
                flux[i] = np.sum(As * u - bs)
            else:
                flux[i] = self.comuteFluxOnRobin(u, faces, dS, bdrycond.fct[color], bdrycond.param[color])
        return flux
    def interpolate(self, f):
        x, y, z = self.mesh.pointsf.T
        return f(x, y, z)
    def interpolateCell(self, f):
        if isinstance(f, dict):
            b = np.zeros(self.mesh.ncells)
            for label, fct in f.items():
                if fct is None: continue
                cells = self.mesh.cellsoflabel[label]
                xc, yc, zc = self.mesh.pointsc[cells].T
                b[cells] = fct(xc, yc, zc)
            return b
        else:
            xc, yc, zc = self.mesh.pointsc.T
            return f(xc, yc, zc)
    def interpolateBoundary(self, colors, f):
        """
        :param colors: set of colors to interpolate
        :param f: ditct of functions
        :return:
        """
        b = np.zeros(self.mesh.nfaces)
        for color in colors:
            if not color in f or not f[color]: continue
            faces = self.mesh.bdrylabels[color]
            normalsS = self.mesh.normals[faces]
            dS = linalg.norm(normalsS,axis=1)
            normalsS = normalsS/dS[:,np.newaxis]
            nx, ny, nz = normalsS.T
            x, y, z = self.mesh.pointsf[faces].T
            # constant normal on whole boundary part !!
            nx, ny, nz = np.mean(normalsS, axis=0)
            try:
                b[faces] = f[color](x, y, z, nx, ny, nz)
            except:
                b[faces] = f[color](x, y, z)
        return b
    def massDotCell(self, b, f, coeff=1):
        assert f.shape[0] == self.mesh.ncells
        dimension, facesOfCells, dV = self.mesh.dimension, self.mesh.facesOfCells, self.mesh.dV
        massloc = 1/(dimension+1)
        np.add.at(b, facesOfCells, (massloc*coeff*dV*f)[:, np.newaxis])
        return b
    def massDot(self, b, f, coeff=1):
        dim, facesOfCells, dV = self.mesh.dimension, self.mesh.facesOfCells, self.mesh.dV
        scalemass = (2-dim) / (dim+1) / (dim+2)
        massloc = np.tile(scalemass, (self.nloc,self.nloc))
        massloc.reshape((self.nloc*self.nloc))[::self.nloc+1] = (2-dim + dim*dim) / (dim+1) / (dim+2)
        r = np.einsum('n,kl,nl->nk', coeff*dV, massloc, f[facesOfCells])
        np.add.at(b, facesOfCells, r)
        return b




    def computeMassMatrixSupg(self, xd, coeff=1):
        raise NotImplemented(f"computeMassMatrixSupg")
    def comptuteMatrixTransport(self, beta, betaC, ld, colors=None):
        raise NotImplemented(f"comptuteMatrixTransport")
    def massDotSupg(self, b, f, xd):
        raise NotImplemented(f"massDotSupg")
    def massDotBoundary(self, b, f, colors=None, coeff=1, lumped=False):
        if colors is None: colors = self.mesh.bdrylabels.keys()
        for color in colors:
            faces = self.mesh.bdrylabels[color]
            normalsS = self.mesh.normals[faces]
            dS = linalg.norm(normalsS, axis=1)
            if isinstance(coeff, (int,float)): scalemass = coeff
            elif isinstance(coeff, dict): scalemass = coeff[color]
            else:
                assert coeff.shape[0]==self.mesh.nfaces
                scalemass = 1
                dS *= coeff[faces]
            b[faces] += scalemass *dS*f[faces]
        return b

    def formDiffusion(self, du, u, coeff):
        raise NotImplemented(f"formDiffusion")
    def computeRhsMass(self, b, rhs, mass):
        raise NotImplemented(f"computeRhsMass")
    def computeRhsCell(self, b, rhscell):
        raise NotImplemented(f"computeRhsCell")
    def computeRhsPoint(self, b, rhspoint):
        raise NotImplemented(f"computeRhsPoint")
    def computeRhsBoundary(self, b, bdrycond, types):
        normals =  self.mesh.normals
        scale = 1 / self.mesh.dimension
        for color, faces in self.mesh.bdrylabels.items():
            if bdrycond.type[color] not in types: continue
            if not color in bdrycond.fct or bdrycond.fct[color] is None: continue
            normalsS = normals[faces]
            dS = linalg.norm(normalsS,axis=1)
            normalsS = normalsS/dS[:,np.newaxis]
            xf, yf, zf = self.mesh.pointsf[faces].T
            nx, ny, nz = normalsS.T
            b[faces] += scale * bdrycond.fct[color](xf, yf, zf, nx, ny, nz) * dS
        return b
    def computeRhsBoundaryMass(self, b, bdrycond, types, mass):
        raise NotImplemented(f"")




    def computeBdryFct(self, u, colors):
        raise NotImplemented(f"")

    def computePointValues(self, u, colors):
        raise NotImplemented(f"")

    def computeMeanValues(self, u, colors):
        raise NotImplemented(f"")

    def computeMeanValue(self, u, color):
        raise NotImplemented(f"")

    #------------------------------
    def test(self):
        import scipy.sparse.linalg as splinalg
        colors = mesh.bdrylabels.keys()
        bdrydata = self.prepareBoundary(colorsdir=colors)
        A = self.computematrixDiffusion(coeff=1)
        A, bdrydata = self.matrixBoundary(A, method='trad', bdrydata=bdrydata)
        b = np.zeros(self.nunknowns())
        rhs = np.vectorize(lambda x,y,z: 1)
        fp1 = self.interpolateCell(rhs)
        self.massDotCell(b, fp1, coeff=1)
        b = self.vectorBoundaryZero(b, bdrydata)
        return self.tonode(splinalg.spsolve(A, b))


# ------------------------------------- #

if __name__ == '__main__':
    from simfempy.meshes import testmeshes
    from simfempy.meshes import plotmesh
    import matplotlib.pyplot as plt

    mesh = testmeshes.backwardfacingstep(h=0.2)
    fem = CR1(mesh)
    u = fem.test()
    plotmesh.meshWithBoundaries(mesh)
    plotmesh.meshWithData(mesh, point_data=u, title="P1 Test", alpha=1)
    plt.show()