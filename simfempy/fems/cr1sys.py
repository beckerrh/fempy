# -*- coding: utf-8 -*-
"""
Created on Sun Dec  4 18:14:29 2016

@author: becker
"""

import numpy as np
import scipy.linalg as linalg
import scipy.sparse as sparse
from simfempy.fems import femsys, cr1
from simfempy.tools import barycentric, npext

#=================================================================#
class CR1sys(femsys.Femsys):
    def __init__(self, ncomp, mesh=None):
        super().__init__(cr1.CR1(mesh=mesh), ncomp, mesh)
    def setMesh(self, mesh):
        super().setMesh(mesh)
        # raise ValueError(f"CR1sys setMesh {self.mesh=}")
        # self.mesh.constructInnerFaces()
    def tonode(self, u):
        ncomp, nnodes = self.ncomp, self.mesh.nnodes
        unodes = np.zeros(ncomp*nnodes)
        for i in range(ncomp):
            unodes[i::ncomp] = self.fem.tonode(u[i::ncomp])
        return unodes
    def matrixBoundary(self, A, bdrydata, method):
        facesdirflux, facesinner, facesdirall, colorsdir = bdrydata.facesdirflux, bdrydata.facesinner, bdrydata.facesdirall, bdrydata.colorsdir
        x, y, z = self.mesh.pointsf.T
        nfaces, ncomp = self.mesh.nfaces, self.ncomp
        for color, faces in facesdirflux.items():
            ind = np.repeat(ncomp * faces, ncomp)
            for icomp in range(ncomp): ind[icomp::ncomp] += icomp
            nb = faces.shape[0]
            help = sparse.dok_matrix((ncomp *nb, ncomp * nfaces))
            for icomp in range(ncomp):
                for i in range(nb): help[icomp + ncomp * i, icomp + ncomp * faces[i]] = 1
            bdrydata.Asaved[color] = help.dot(A)
        indin = np.repeat(ncomp * facesinner, ncomp)
        for icomp in range(ncomp): indin[icomp::ncomp] += icomp
        inddir = np.repeat(ncomp * facesdirall, ncomp)
        for icomp in range(ncomp): inddir[icomp::ncomp] += icomp
        bdrydata.A_inner_dir = A[indin, :][:, inddir]
        if method == 'strong':
            help = np.ones((ncomp * nfaces))
            help[inddir] = 0
            help = sparse.dia_matrix((help, 0), shape=(ncomp * nfaces, ncomp * nfaces))
            A = help.dot(A.dot(help))
            help = np.zeros((ncomp * nfaces))
            help[inddir] = 1.0
            help = sparse.dia_matrix((help, 0), shape=(ncomp * nfaces, ncomp * nfaces))
            A += help
        else:
            bdrydata.A_dir_dir = A[inddir, :][:, inddir]
            help = np.ones((ncomp * nfaces))
            help[inddir] = 0
            help = sparse.dia_matrix((help, 0), shape=(ncomp * nfaces, ncomp * nfaces))
            help2 = np.zeros((ncomp * nfaces))
            help2[inddir] = 1
            help2 = sparse.dia_matrix((help2, 0), shape=(ncomp * nfaces, ncomp * nfaces))
            A = help.dot(A.dot(help)) + help2.dot(A.dot(help2))
        return A
    def vectorBoundary(self, b, bdryfct, bdrydata, method):
        facesdirflux, facesinner, facesdirall, colorsdir = bdrydata.facesdirflux, bdrydata.facesinner, bdrydata.facesdirall, bdrydata.colorsdir
        x, y, z = self.mesh.pointsf.T
        nfaces, ncomp = self.mesh.nfaces, self.ncomp
        for color, faces in facesdirflux.items():
            ind = np.repeat(ncomp * faces, ncomp)
            for icomp in range(ncomp): ind[icomp::ncomp] += icomp
            bdrydata.bsaved[color] = b[ind]
        indin = np.repeat(ncomp * facesinner, ncomp)
        for icomp in range(ncomp): indin[icomp::ncomp] += icomp
        inddir = np.repeat(ncomp * facesdirall, ncomp)
        for icomp in range(ncomp): inddir[icomp::ncomp] += icomp
        help = np.zeros_like(b)
        for color in colorsdir:
            faces = self.mesh.bdrylabels[color]
            if color in bdryfct:
                dirichlets = bdryfct[color](x[faces], y[faces], z[faces])
                for icomp in range(ncomp):
                    help[icomp + ncomp * faces] = dirichlets[icomp]
        b[indin] -= bdrydata.A_inner_dir * help[inddir]
        if method == 'strong':
            b[inddir] = help[inddir]
            # print(f"{b[inddir]=}")
        else:
            b[inddir] = bdrydata.A_dir_dir * help[inddir]
        return b
        # for color in colorsdir:
        #     faces = self.mesh.bdrylabels[color]
        #     if color in bdryfct.keys():
        #         dirichlets = bdryfct[color](x[faces], y[faces], z[faces])
        #         for icomp in range(ncomp):
        #             u[icomp + ncomp * faces] = dirichlets[icomp]
        #     else:
        #         for icomp in range(ncomp):
        #             u[icomp + ncomp * faces] = 0
        # b[indin] -= bdrydata.A_inner_dir * u[inddir]
        # if self.fem.dirichletmethod == 'strong':
        #     b[inddir] = u[inddir]
        # else:
        #     b[inddir] = bdrydata.A_dir_dir * u[inddir]
        # # print(f"{b=}")
        # return b, u, bdrydata
    def computeRhsBoundary(self, b, colors, bdryfct):
        for color in colors:
            if not color in bdryfct or not bdryfct[color]: continue
            faces = self.mesh.bdrylabels[color]
            normalsS = self.mesh.normals[faces]
            dS = linalg.norm(normalsS,axis=1)
            xf, yf, zf = self.mesh.pointsf[faces].T
            nx, ny, nz = normalsS.T / dS
            neumanns = bdryfct[color](xf, yf, zf, nx, ny, nz)
            for i in range(self.ncomp):
                bS = dS * neumanns[i]
                indices = i + self.ncomp * faces
                b[indices] += bS
        return b
    def computeMatrixDivergence(self):
        nfaces, ncells, ncomp, dV = self.mesh.nfaces, self.mesh.ncells, self.ncomp, self.mesh.dV
        nloc, cellgrads, facesOfCells = self.fem.nloc, self.fem.cellgrads, self.mesh.facesOfCells
        rowsB = np.repeat(np.arange(ncells), ncomp * nloc).reshape(-1)
        colsB = ncomp*np.repeat(facesOfCells, ncomp).reshape(ncells * nloc, ncomp) + np.arange(ncomp)
        mat = np.einsum('nkl,n->nkl', cellgrads[:, :, :ncomp], dV)
        B = sparse.coo_matrix((mat.reshape(-1), (rowsB, colsB.ravel())),shape=(ncells, nfaces * ncomp)).tocsr()
        return B
    def computeMatrixLaplace(self, mucell):
        nfaces, ncells, ncomp, dV = self.mesh.nfaces, self.mesh.ncells, self.ncomp, self.mesh.dV
        nloc, rows, cols, cellgrads = self.fem.nloc, self.rowssys, self.colssys, self.fem.cellgrads
        mat = np.zeros(shape=rows.shape, dtype=float).reshape(ncells, ncomp * nloc, ncomp * nloc)
        for i in range(ncomp):
            mat[:, i::ncomp, i::ncomp] += (np.einsum('nkj,nlj->nkl', cellgrads, cellgrads).T * dV * mucell).T
        A = sparse.coo_matrix((mat.ravel(), (rows, cols)), shape=(ncomp*nfaces, ncomp*nfaces)).tocsr()
        return A
    def computeMatrixElasticity(self, mucell, lamcell):
        nfaces, ncells, ncomp, dV = self.mesh.nfaces, self.mesh.ncells, self.ncomp, self.mesh.dV
        nloc, rows, cols, cellgrads = self.fem.nloc, self.rowssys, self.colssys, self.fem.cellgrads
        mat = np.zeros(shape=rows.shape, dtype=float).reshape(ncells, ncomp * nloc, ncomp * nloc)
        for i in range(ncomp):
            for j in range(self.ncomp):
                mat[:, i::ncomp, j::ncomp] += (np.einsum('nk,nl->nkl', cellgrads[:, :, i], cellgrads[:, :, j]).T * dV * lamcell).T
                mat[:, i::ncomp, j::ncomp] += (np.einsum('nk,nl->nkl', cellgrads[:, :, j], cellgrads[:, :, i]).T * dV * mucell).T
                mat[:, i::ncomp, i::ncomp] += (np.einsum('nk,nl->nkl', cellgrads[:, :, j], cellgrads[:, :, j]).T * dV * mucell).T
        A = sparse.coo_matrix((mat.ravel(), (rows, cols)), shape=(ncomp*nfaces, ncomp*nfaces)).tocsr()
        A += self.computeMatrixKorn(mucell)
        return A
    def computeMatrixKorn(self, mucell):
        ncomp = self.ncomp
        dimension, dV, ndofs = self.mesh.dimension, self.mesh.dV, self.nunknowns()
        nloc, dofspercell, nall = self.nlocal(), self.dofspercell(), ncomp*ndofs
        ci0 = self.mesh.cellsOfInteriorFaces[:,0]
        ci1 = self.mesh.cellsOfInteriorFaces[:,1]
        assert np.all(ci1>=0)
        normalsS = self.mesh.normals[self.mesh.innerfaces]
        dS = linalg.norm(normalsS, axis=1)
        faces = self.mesh.faces[self.mesh.innerfaces]
        ind0 = npext.positionin(faces, self.mesh.simplices[ci0])
        ind1 = npext.positionin(faces, self.mesh.simplices[ci1])
        fi0 = np.take_along_axis(self.mesh.facesOfCells[ci0], ind0, axis=1)
        fi1 = np.take_along_axis(self.mesh.facesOfCells[ci1], ind1, axis=1)
        d = self.mesh.dimension
        massloc = barycentric.crbdryothers(d)
        if isinstance(mucell,(int,float)):
            scale = mucell*dS/(dV[ci0]+ dV[ci1])
        else:
            scale = (mucell[ci0] + mucell[ci1]) * dS / (dV[ci0] + dV[ci1])
        scale *= 8
        A = sparse.coo_matrix((nall, nall))
        mat = np.einsum('n,kl->nkl', dS*scale, massloc).reshape(-1)
        for icomp in range(ncomp):
            d0 = ncomp*fi0+icomp
            d1 = ncomp*fi1+icomp
            rows0 = d0.repeat(nloc-1)
            cols0 = np.tile(d0,nloc-1).reshape(-1)
            rows1 = d1.repeat(nloc-1)
            cols1 = np.tile(d1,nloc-1).reshape(-1)
            # print(f"{mat.shape=}")
            # print(f"{rows0.shape=}")
            # print(f"{cols0.shape=}")
            # print(f"{fi0.shape=}")
            # print(f"{fi1.shape=}")
            A += sparse.coo_matrix((mat, (rows0, cols0)), shape=(nall, nall))
            A += sparse.coo_matrix((-mat, (rows0, cols1)), shape=(nall, nall))
            A += sparse.coo_matrix((-mat, (rows1, cols0)), shape=(nall, nall))
            A += sparse.coo_matrix((mat, (rows1, cols1)), shape=(nall, nall))
        return A
    def computeBdryNormalFlux(self, u, colors, bdrydata):
        flux, omega = np.zeros(shape=(len(colors),self.ncomp)), np.zeros(len(colors))
        for i,color in enumerate(colors):
            faces = self.mesh.bdrylabels[color]
            normalsS = self.mesh.normals[faces]
            dS = linalg.norm(normalsS, axis=1)
            omega[i] = np.sum(dS)
            bs, As = bdrydata.bsaved[color], bdrydata.Asaved[color]
            res = bs - As * u
            for icomp in range(self.ncomp):
                flux[i, icomp] = np.sum(res[icomp::self.ncomp])
        return flux

# ------------------------------------- #

if __name__ == '__main__':
    from simfempy.meshes import testmeshes
    from simfempy.meshes import plotmesh
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec

    mesh = testmeshes.backwardfacingstep(h=0.2)
    fem = CR1sys(ncomp=2, mesh=mesh)
    u = fem.test()
    point_data = fem.getPointData(u)
    fig = plt.figure(figsize=(10, 8))
    outer = gridspec.GridSpec(1, 2, wspace=0.2, hspace=0.2)
    plotmesh.meshWithBoundaries(mesh, fig=fig, outer=outer[0])
    plotmesh.meshWithData(mesh, point_data=point_data, title="P1 Test", alpha=1, fig=fig, outer=outer[1])
    plt.show()
