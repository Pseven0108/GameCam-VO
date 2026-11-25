"""Seeded linear least-squares fixtures; every residual touches one depth only."""
from dataclasses import dataclass
import numpy as np
from cadp_cpu import Geometry


@dataclass
class Fixture:
    geometry: Geometry
    bx: np.ndarray
    bg: np.ndarray
    disparity: np.ndarray
    mono_disparity: np.ndarray
    observation_count: np.ndarray
    frame_ids: np.ndarray
    jacobian_pose: np.ndarray
    jacobian_depth: np.ndarray
    residual: np.ndarray


def make_fixture(seed=43, npose=6, ndepth=24, observations_per_depth=3,
                 geometry_scale=1.0, pose_anchor=0.02, eta_scale=0.003):
    rng = np.random.default_rng(seed)
    nobs = ndepth*observations_per_depth
    jp = rng.normal(size=(nobs,npose))*0.2*np.sqrt(geometry_scale)
    depth_index = np.repeat(np.arange(ndepth),observations_per_depth)
    jd = np.zeros((nobs,ndepth))
    jd[np.arange(nobs),depth_index] = rng.uniform(0.1,0.6,size=nobs)*np.sqrt(geometry_scale)
    residual = rng.normal(0,0.05,size=nobs)
    a = jp.T@jp + np.eye(npose)*pose_anchor
    e = jp.T@jd
    cg = np.einsum('ij,ij->j',jd,jd)
    eta = eta_scale*rng.uniform(0.4,2.0,ndepth)
    d = rng.uniform(0.05,3.0,ndepth)
    dm = d*np.exp(rng.normal(0,0.3,ndepth))
    dm[::7] = 0.0
    dm[1::11] = -0.5
    return Fixture(Geometry(a,e,cg,eta),jp.T@residual,jd.T@residual,d,dm,
                   np.bincount(depth_index,minlength=ndepth),
                   np.arange(ndepth)//max(1,ndepth//3),jp,jd,residual)


def large_fixture(seed=20261126, npose=72, ndepth=54000):
    """Dimension-matched SYNTHETIC system, not recovered R3 data.

    Build A=Z Z^T + anchor and E=Z sqrt(Cg). This PSD geometry is a
    Gram matrix with one depth observation per column and zero residual.
    """
    rng = np.random.default_rng(seed)
    z = rng.normal(size=(npose,ndepth))*0.003
    cg = rng.uniform(0.005,0.1,ndepth)
    e = z*np.sqrt(cg)
    a = z@z.T+np.eye(npose)*0.05
    eta = rng.uniform(0.0001,0.01,ndepth)
    d = rng.uniform(0.05,1.0,ndepth)
    return Geometry(a,e,cg,eta),d,np.arange(ndepth)//3600
