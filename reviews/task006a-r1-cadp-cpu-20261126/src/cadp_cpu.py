"""Independent CPU float64 CADP mathematics, NOT an implementation of native BA.

Inputs are synthetic aggregated normal-equation blocks. No production imports,
autograd, relinearization, native-U update, tensor archives or runtime hooks.
"""
from dataclasses import dataclass
from typing import Optional, Sequence
import numpy as np
from scipy.linalg import solve_triangular, cho_solve

GAMMA_DEPTH = 0.01


class DomainError(ValueError):
    """Input is outside the explicitly supported mathematical domain."""


class NumericalError(ValueError):
    """No certified SPD solve; never silently jitter, clip or pseudoinvert."""


def finite_array(x, name, ndim=None):
    x = np.asarray(x, dtype=np.float64)
    if ndim is not None and x.ndim != ndim:
        raise DomainError(f'{name}: expected rank {ndim}, got {x.ndim}')
    if not np.isfinite(x).all():
        raise DomainError(f'{name}: non-finite input')
    return x


def symmetric(x, name):
    x = finite_array(x, name, 2)
    if x.shape[0] != x.shape[1]:
        raise DomainError(f'{name}: not square')
    scale = max(1.0, float(np.linalg.norm(x, ord=np.inf))) if x.size else 1.0
    if x.size and np.max(np.abs(x - x.T)) > 1e-12 * scale:
        raise DomainError(f'{name}: materially asymmetric')
    # Floating-point roundoff only. Not a repair for an asymmetric input system.
    return (x + x.T) * 0.5


@dataclass(frozen=True)
class Geometry:
    A: np.ndarray
    E: np.ndarray
    Cg: np.ndarray
    eta: np.ndarray

    def checked(self):
        a = symmetric(self.A, 'A')
        e = finite_array(self.E, 'E', 2)
        cg = finite_array(self.Cg, 'Cg', 1)
        eta = finite_array(self.eta, 'eta', 1)
        if e.shape != (a.shape[0], cg.size) or eta.shape != cg.shape or cg.size == 0:
            raise DomainError('A/E/Cg/eta dimension mismatch or empty depth set')
        if (cg < 0).any() or (eta < 0).any():
            raise DomainError('Negative geometric depth curvature or eta')
        return Geometry(a.copy(), e.copy(), cg.copy(), eta.copy())


@dataclass(frozen=True)
class SchurFactor:
    A: np.ndarray
    E: np.ndarray
    C: np.ndarray
    q: np.ndarray
    H: np.ndarray
    damping: np.ndarray
    Hd: np.ndarray
    L: np.ndarray
    condition: float
    minimum_eigenvalue: float

    def solve_pose(self, rhs):
        rhs = finite_array(rhs, 'pose rhs')
        if rhs.ndim not in (1, 2) or rhs.shape[0] != self.Hd.shape[0]:
            raise DomainError('pose rhs dimension mismatch')
        if not self.Hd.size:
            return rhs.copy()
        out = cho_solve((self.L, True), rhs, check_finite=False)
        if not np.isfinite(out).all():
            raise NumericalError('Non-finite pose solution')
        return out


def factor_schur(A, E, C, lm=1e-4, ep=0.1, max_condition=1e12):
    """Native order: H=A-E/C@E.T, THEN diagonal ep + lm*diag(H).

    The condition limit is a CPU research acceptance policy, not a native BA
    parameter. It is never modified automatically to make a failed case pass.
    """
    a = symmetric(A, 'A')
    e = finite_array(E, 'E', 2)
    c = finite_array(C, 'C', 1)
    params = finite_array([lm, ep, max_condition], 'factor parameters')
    if e.shape != (a.shape[0], c.size) or not c.size:
        raise DomainError('Schur dimensions')
    if (c <= 0).any() or lm < 0 or ep < 0 or max_condition < 1:
        raise DomainError('Require C>0, lm/ep>=0, max_condition>=1')
    with np.errstate(over='raise', divide='raise', invalid='raise'):
        try:
            q = 1.0 / c
            h = symmetric(a - (e * q) @ e.T, 'Schur H')
            damping = ep + lm * np.diag(h)
            hd = h + np.diag(damping)
        except FloatingPointError as exc:
            raise NumericalError('Schur arithmetic overflow') from exc
    if not h.size:
        return SchurFactor(a,e,c,q,h,damping,hd,np.empty((0,0)),1.0,float('inf'))
    h_eig = np.linalg.eigvalsh(h)
    scale = max(1.0, float(np.linalg.norm(h, ord=2)))
    if h_eig[0] < -1e-10 * scale:
        raise NumericalError('Inconsistent geometry: undamped Schur is indefinite')
    if (damping < 0).any():
        raise NumericalError('Negative pose damping')
    eig = np.linalg.eigvalsh(hd)
    if not np.isfinite(eig).all() or eig[0] <= 0:
        raise NumericalError('Damped Schur is not SPD')
    cond = float(eig[-1] / eig[0])
    if not np.isfinite(cond) or cond > max_condition:
        raise NumericalError(f'Damped Schur too ill-conditioned: {cond:.6g}')
    try:
        l = np.linalg.cholesky(hd)
    except np.linalg.LinAlgError as exc:
        raise NumericalError('Cholesky failed') from exc
    return SchurFactor(a,e,c,q,h,damping,hd,l,cond,float(eig[0]))


def prior_off(geometry, lm=1e-4, ep=0.1, max_condition=1e12):
    """No mono prior, m, alpha, rho or b is accepted by this API."""
    g = geometry.checked()
    return factor_schur(g.A, g.E, g.Cg + g.eta, lm, ep, max_condition)


def _projected_columns(factor, start, stop):
    rhs = factor.E[:, start:stop] * factor.q[start:stop]
    if not factor.Hd.size:
        return rhs
    return solve_triangular(factor.L, rhs, lower=True, check_finite=False)


def full_covariance(factor, max_depth=2048):
    """Small-system oracle. The dense n_depth^2 allocation is deliberately capped."""
    if factor.q.size > max_depth:
        raise DomainError('Full covariance is small-system-only; use blocked_diagonal')
    f = _projected_columns(factor, 0, factor.q.size)
    return np.diag(factor.q) + f.T @ f


def blocked_diagonal(factor, block_size=256):
    """Exact marginal diagonal, retaining ALL pose correlations across blocks."""
    if not isinstance(block_size, (int, np.integer)) or isinstance(block_size, bool) or block_size <= 0:
        raise DomainError('block_size must be a positive integer')
    result = np.empty_like(factor.q)
    for start in range(0, factor.q.size, block_size):
        end = min(start + block_size, factor.q.size)
        f = _projected_columns(factor, start, end)
        result[start:end] = factor.q[start:end] + np.einsum('ij,ij->j', f, f)
    if not np.isfinite(result).all() or (result <= 0).any():
        raise NumericalError('Invalid covariance diagonal')
    return result


def covariance_block(factor, rows, cols):
    rows = np.asarray(rows)
    cols = np.asarray(cols)
    for ids in (rows, cols):
        if ids.ndim != 1 or ids.dtype.kind not in 'iu' or (ids < 0).any() or (ids >= factor.q.size).any():
            raise DomainError('Covariance block index outside depth set')
    fr = factor.E[:, rows] * factor.q[rows]
    fc = factor.E[:, cols] * factor.q[cols]
    if factor.Hd.size:
        fr = solve_triangular(factor.L, fr, lower=True, check_finite=False)
        fc = solve_triangular(factor.L, fc, lower=True, check_finite=False)
    return fr.T @ fc + (rows[:,None] == cols[None,:]) * factor.q[rows,None]


def joint_precision(factor):
    """Precision whose inverse the formula represents: adds damping to pose block."""
    return np.block([[factor.A + np.diag(factor.damping), factor.E],
                     [factor.E.T, np.diag(factor.C)]])


def native_depth_terms(Cg, bg, eta, d, dm, enabled, alpha=GAMMA_DEPTH):
    """Independent scalar-loop CPU transcription of the native D0/D1 equations.

    Deliberately not implemented by calling the CADP interpolation function.
    Equivalence is defined for finite data only; nonfinite native propagation is
    NOT silently relabeled as valid math.
    """
    cg,bg,eta,d,dm = [finite_array(x,n,1) for x,n in zip((Cg,bg,eta,d,dm),('Cg','bg','eta','d','dm'))]
    if any(x.shape != cg.shape for x in (bg,eta,d,dm)):
        raise DomainError('Native terms shape mismatch')
    if not isinstance(enabled, (bool, np.bool_)) or not np.isfinite(alpha) or alpha < 0:
        raise DomainError('Invalid native enable/alpha')
    c = np.empty_like(cg)
    b = np.empty_like(cg)
    for j in range(cg.size):
        if enabled and dm[j] > 0:
            c[j] = cg[j] + alpha
            b[j] = bg[j] - alpha * (d[j] - dm[j])
        else:
            c[j] = cg[j] + eta[j]
            b[j] = bg[j]
    return c,b


def cadp_depth_terms(Cg, bg, eta, d, dm, rho, alpha=GAMMA_DEPTH):
    cg,bg,eta,d,dm = [finite_array(x,n,1) for x,n in zip((Cg,bg,eta,d,dm),('Cg','bg','eta','d','dm'))]
    if any(x.shape != cg.shape for x in (bg,eta,d,dm)):
        raise DomainError('CADP terms shape mismatch')
    if (cg < 0).any() or (eta < 0).any() or not np.isfinite(alpha) or alpha < 0:
        raise DomainError('Negative curvature/eta/alpha')
    r = finite_array(rho,'rho')
    if r.ndim == 0:
        r = np.full_like(cg, float(r))
    if r.shape != cg.shape or (r < 0).any() or (r > 1).any():
        raise DomainError('rho must be scalar or per-pixel [0,1]')
    m = (dm > 0).astype(np.float64)
    z = m*r
    c = cg + z*alpha + (1.0-z)*eta
    b = bg - z*alpha*(d-dm)
    if not np.isfinite(c).all() or not np.isfinite(b).all():
        raise NumericalError('Nonfinite CADP terms')
    return c,b


def solve_ba_step(geometry, bx, bdepth, curvature, lm=1e-4, ep=0.1):
    """Mathematical joint-system solve, NOT the ix<=0 native depth backsub branch."""
    g = geometry.checked()
    bx = finite_array(bx,'bx',1)
    bd = finite_array(bdepth,'bd',1)
    if bx.shape != (g.A.shape[0],) or bd.shape != g.Cg.shape:
        raise DomainError('BA rhs dimensions')
    fac = factor_schur(g.A,g.E,curvature,lm,ep)
    dx = fac.solve_pose(bx-g.E@(fac.q*bd))
    dz = fac.q*(bd-g.E.T@dx)
    return dx,dz,fac


def native_guarded_backsub(E, q, bdepth, dx, pose_dim=6):
    """CPU algebraic transcription of EvT6x1's ix<=0 exclusion.

    Valid E assembly requires target<t1. The first FREE pose's whole tangent
    block is omitted from native depth backsub, though it is present in Schur.
    This diagnostic does not replace the ideal joint-system covariance formula,
    and does not reproduce float32 kernels or atomic summation order.
    """
    e=finite_array(E,'E',2); q=finite_array(q,'q',1)
    b=finite_array(bdepth,'bdepth',1); dx=finite_array(dx,'dx',1)
    if not isinstance(pose_dim,int) or pose_dim<1 or e.shape!=(dx.size,q.size) or b.shape!=q.shape:
        raise DomainError('Guarded native backsub dimensions')
    if dx.size % pose_dim:
        raise DomainError('Pose vector must consist of whole native tangent blocks')
    return q*(b-e[pose_dim:].T@dx[pose_dim:])


def stable_sigmoid(u, k, tau):
    vals = finite_array(u,'uncertainty')
    if not np.isfinite(k) or k <= 0 or not np.isfinite(tau):
        raise DomainError('Require finite k>0 and finite tau')
    with np.errstate(over='ignore', under='ignore'):
        z = k*(vals-tau)
        out = np.empty_like(z)
        positive = z >= 0
        out[positive] = 1.0/(1.0+np.exp(-z[positive]))
        expz = np.exp(z[~positive])
        out[~positive] = expz/(1.0+expz)
    return out


@dataclass(frozen=True)
class FrameStatistic:
    frame_id: int
    valid_pixels: int
    total_pixels: int
    nonpositive_or_nonfinite_disparity: int
    unsupported_pixels: int
    weak_curvature_pixels_included: int
    uncertainty: Optional[float]
    rho: Optional[float]
    status: str


def frame_statistics(variance, disparity, frame_ids, observation_count, geometric_curvature,
                     *, k, tau, epsilon=1e-6, min_valid=1):
    """V_f: finite positive d, positive count, finite positive marginal variance.

    No mono/prior mask. Cg=0 is INCLUDED when an observation exists. Empty or
    insufficient support yields None, never an invented fallback prior weight.
    Median is NumPy's midpoint median for even N, not Torch's lower median.
    """
    var = finite_array(variance,'variance',1)
    cg = finite_array(geometric_curvature,'Cg',1)
    d = np.asarray(disparity,dtype=np.float64)
    ids = np.asarray(frame_ids)
    count = np.asarray(observation_count)
    if d.shape != var.shape or cg.shape != var.shape or ids.shape != var.shape or count.shape != var.shape:
        raise DomainError('Frame statistic dimensions')
    if ids.dtype.kind not in 'iu' or count.dtype.kind not in 'iu' or (count<0).any():
        raise DomainError('Frame IDs/counts must be integer and counts nonnegative')
    if (var <= 0).any() or (cg < 0).any() or not np.isfinite(epsilon) or epsilon <= 0:
        raise DomainError('Invalid variance/epsilon/Cg')
    if not isinstance(min_valid,int) or isinstance(min_valid,bool) or min_valid < 1:
        raise DomainError('min_valid must be a positive integer')
    stable_sigmoid(np.array([0.0]),k,tau)  # validate explicit, uncalibrated parameters
    valid_d = np.isfinite(d) & (d>0)
    valid = valid_d & (count>0)
    output = []
    for frame in np.unique(ids):
        own = ids == frame
        v = valid & own
        n = int(v.sum())
        u = None
        rho = None
        status = 'NO_VALID_PIXELS' if n == 0 else 'INSUFFICIENT_SUPPORT' if n < min_valid else 'OK_SYNTHETIC_DOMAIN'
        if status == 'OK_SYNTHETIC_DOMAIN':
            relative = np.sqrt(var[v])/(np.abs(d[v])+epsilon)
            if not np.isfinite(relative).all():
                raise NumericalError('Relative standard deviation overflow')
            u = float(np.median(relative))
            rho = float(stable_sigmoid(np.array([u]),k,tau)[0])
        output.append(FrameStatistic(int(frame),n,int(own.sum()),int((own&~valid_d).sum()),
                     int((own&(count==0)).sum()),int((v&(cg==0)).sum()),u,rho,status))
    return output


def broadcast_frame_rho(statistics: Sequence[FrameStatistic], frame_ids):
    ids = np.asarray(frame_ids)
    if ids.ndim != 1 or ids.dtype.kind not in 'iu':
        raise DomainError('frame_ids must be integer vector')
    lookup = {}
    for item in statistics:
        if item.frame_id in lookup or item.rho is None or not np.isfinite(item.rho) or not 0 <= item.rho <= 1:
            raise DomainError('Missing, duplicate or invalid frame rho; stop instead of fallback')
        lookup[item.frame_id] = item.rho
    if any(int(i) not in lookup for i in ids):
        raise DomainError('Frame absent from rho table')
    return np.array([lookup[int(i)] for i in ids],dtype=np.float64)


@dataclass(frozen=True)
class AdaptivePlan:
    variance: np.ndarray
    frame_statistics: tuple
    pixel_rho: np.ndarray
    frame_ids: np.ndarray


def build_adaptive_plan(geometry, disparity, frame_ids, observation_count,
                        *, k, tau, epsilon=1e-6, min_valid=1, block_size=256,
                        lm=1e-4, ep=0.1):
    """First-linearization-only plan. No mono depth/alpha/gradient API inputs.

    The caller reuses pixel_rho for a BA call's subsequent iterations. This CPU
    object models that contract, but is not connected to any native iteration.
    """
    g=geometry.checked()
    variance=blocked_diagonal(prior_off(g,lm,ep),block_size)
    stats=frame_statistics(variance,disparity,frame_ids,observation_count,g.Cg,
                            k=k,tau=tau,epsilon=epsilon,min_valid=min_valid)
    rho=broadcast_frame_rho(stats,frame_ids)
    ids=np.array(frame_ids,copy=True)
    for a in (variance,rho,ids):
        a.setflags(write=False)
    return AdaptivePlan(variance,tuple(stats),rho,ids)


def assemble_cross_blocks(rows, target_pose_ids, source_depth_ids, depth_ids, t0, t1, pose_dim=6):
    """Add Erows by IDs; K may differ from P; retain depths of fixed source poses."""
    r = finite_array(rows,'Erows',3)
    target = np.asarray(target_pose_ids)
    source = np.asarray(source_depth_ids)
    depth = np.asarray(depth_ids)
    if not isinstance(t0,int) or not isinstance(t1,int) or t1<t0 or pose_dim<1:
        raise DomainError('Invalid pose interval/dimension')
    if r.shape[1] != pose_dim or target.shape != (len(r),) or source.shape != target.shape:
        raise DomainError('Erows/ID dimensions')
    if any(x.dtype.kind not in 'iu' or x.ndim != 1 for x in (target,source,depth)):
        raise DomainError('IDs must be integer vectors')
    if not depth.size or np.unique(depth).size != depth.size or not np.array_equal(depth,np.sort(depth)):
        raise DomainError('depth_ids must be nonempty unique sorted IDs')
    if (target == t1).any():
        raise DomainError('Native boundary ambiguity: target ID equals exclusive t1')
    lookup = {int(v):i for i,v in enumerate(depth)}
    e = np.zeros(((t1-t0)*pose_dim,len(depth)*r.shape[2]),dtype=np.float64)
    for rr,jj,ii in zip(r,target,source):
        if int(ii) not in lookup:
            raise DomainError('Source depth missing from kx')
        if t0 <= jj < t1:
            p = (int(jj)-t0)*pose_dim
            d0 = lookup[int(ii)]*r.shape[2]
            e[p:p+pose_dim,d0:d0+r.shape[2]] += rr
    return e
