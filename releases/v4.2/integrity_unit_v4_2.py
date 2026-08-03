"""
Stability Engine v4.2 - Integrity Unit holonomic drift scaffold.

This scaffold is intended for audit of math honesty, implementation
defensibility, and alignment with Stability Engine v4 architecture. It should
not be expanded for impressiveness or overclaimed as final canonical code.

Status: runnable prototype scaffold, not a production module.
"""

from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Tuple

import numpy as np


# Stability Engine Thresholds
# MTS-4 / IM-4 - reserved warn/cool thresholds.
#
# NOTE: Declared for v4 architecture alignment only. They are not exercised
# anywhere in this scaffold. Warn/cool threshold integration is deferred.
TAU_WARN = 0.05
TAU_COOL = 0.20


class CoordinateDomain:
    """
    Minimal coordinate-domain stub.

    Defines coordinate admissibility for candidate states. This placeholder
    keeps the scaffold runnable and is expected to be replaced by the real
    domain definition from the Stability Engine v4 coordinate layer.

    With no bounds supplied, every finite coordinate vector is admissible.
    Optional elementwise box bounds may be supplied for basic testing.

    Shape mismatches are rejected explicitly to avoid accidental NumPy
    broadcasting masking invalid coordinate-domain definitions.
    """

    def __init__(
        self,
        lower: Optional[np.ndarray] = None,
        upper: Optional[np.ndarray] = None,
    ):
        self.lower = None if lower is None else np.asarray(lower, dtype=float)
        self.upper = None if upper is None else np.asarray(upper, dtype=float)

        if self.lower is not None and self.lower.ndim != 1:
            raise ValueError(f"lower bound must be a 1-D vector, got {self.lower.shape}")
        if self.upper is not None and self.upper.ndim != 1:
            raise ValueError(f"upper bound must be a 1-D vector, got {self.upper.shape}")
        if self.lower is not None and self.upper is not None:
            if self.lower.shape != self.upper.shape:
                raise ValueError(
                    "lower and upper bounds must have matching shapes: "
                    f"{self.lower.shape} != {self.upper.shape}"
                )
            if np.any(self.lower > self.upper):
                raise ValueError("lower bounds must be less than or equal to upper bounds")

    @property
    def dimension(self) -> Optional[int]:
        """Return the coordinate dimension implied by supplied bounds, if any."""
        if self.lower is not None:
            return int(self.lower.shape[0])
        if self.upper is not None:
            return int(self.upper.shape[0])
        return None

    def is_admissible(self, q: np.ndarray) -> bool:
        """Return True only when q is finite and inside declared bounds."""
        q = np.asarray(q, dtype=float)
        if q.ndim != 1:
            return False
        if not np.all(np.isfinite(q)):
            return False
        if self.lower is not None:
            if q.shape != self.lower.shape:
                return False
            if np.any(q < self.lower):
                return False
        if self.upper is not None:
            if q.shape != self.upper.shape:
                return False
            if np.any(q > self.upper):
                return False
        return True


@dataclass
class CorrectionResult:
    """
    Structured outcome of a minimum-norm correction attempt.

    status is one of:
       "converged"               residuals converged and state is admissible
       "converged_inadmissible"  residuals converged but state left the domain
       "linalg_failure"          a linear-algebra step failed
       "non_finite"              a non-finite intermediate value was produced
       "max_iterations"          iteration budget exhausted without convergence

    state holds the corrected coordinate vector only when status is
    "converged"; it is None for every other status.

    clamped_steps counts iterations whose correction step was capped by
    max_step_norm. A high clamped_steps relative to iterations indicates the
    step cap is throttling convergence rather than the problem being hard.
    """

    status: str
    state: Optional[np.ndarray]
    iterations: int
    residual_norm: float
    clamped_steps: int = 0
    message: str = ""

    @property
    def ok(self) -> bool:
        """Return True only for successful convergence into an admissible state."""
        return self.status == "converged"


def _validate_metric(matrix: np.ndarray, name: str, definiteness: str) -> np.ndarray:
    """
    Validate that matrix is a usable metric matrix.

    definiteness:
       "psd"  symmetric positive semidefinite, valid seminorm weight
       "pd"   symmetric positive definite, valid inner-product metric

    Symmetry and definiteness are checked here so the quadratic forms that
    depend on them are mathematically well posed. Dimension agreement with
    a specific state or constraint count is checked separately by the caller.
    """
    matrix = np.array(matrix, dtype=float, copy=True)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"{name} must be a square 2-D matrix, got shape {matrix.shape}")
    if not np.all(np.isfinite(matrix)):
        raise ValueError(f"{name} must contain only finite values")
    if not np.allclose(matrix, matrix.T, atol=1e-10):
        raise ValueError(f"{name} must be symmetric")

    min_eig = float(np.linalg.eigvalsh(matrix)[0])
    if definiteness == "pd":
        if min_eig <= 1e-12:
            raise ValueError(
                f"{name} must be positive definite "
                f"(minimum eigenvalue {min_eig:.3e})"
            )
    elif definiteness == "psd":
        if min_eig < -1e-10:
            raise ValueError(
                f"{name} must be positive semidefinite "
                f"(minimum eigenvalue {min_eig:.3e})"
            )
    else:
        raise ValueError(f"unknown definiteness requirement: {definiteness!r}")

    return matrix


class IntegrityUnit:
    """
    Integrity Unit prototype for holonomic drift detection and enforcement.

    Maintains clean boundaries between:
      - residual_metric, W_res: matrix for weighting constraint violations.
      - state_metric, W_state: matrix defining the coordinate inner product
        for minimum-norm correction steps.

    Caller must ensure constraint callables are pure and deterministic.
    """

    def __init__(
        self,
        constraints: Iterable[Callable[[np.ndarray], float]],
        constraint_jacobian: Callable[[np.ndarray], np.ndarray],
        domain: Optional[CoordinateDomain] = None,
        max_iterations: int = 50,
        tolerance: float = 1e-6,
        residual_metric: Optional[np.ndarray] = None,  # W_res, shape m x m
        state_metric: Optional[np.ndarray] = None,  # W_state, shape n x n
        max_step_norm: Optional[float] = 0.5,
        state_dim: Optional[int] = None,
    ):
        self.constraints = list(constraints)
        self.jacobian = constraint_jacobian
        self.domain = domain if domain is not None else CoordinateDomain()
        self.max_iter = int(max_iterations)
        self.tol = float(tolerance)
        self.max_step_norm = max_step_norm

        if self.max_iter <= 0:
            raise ValueError("max_iterations must be positive")
        if self.tol <= 0:
            raise ValueError("tolerance must be positive")
        if self.max_step_norm is not None and self.max_step_norm <= 0:
            raise ValueError("max_step_norm must be positive when supplied")

        m = len(self.constraints)
        domain_dim = self.domain.dimension

        # W_res is weighted across constraints, so its dimension m is known
        # at construction and is fully validated here.
        if residual_metric is not None:
            w_res = _validate_metric(residual_metric, "residual_metric", "psd")
            if w_res.shape != (m, m):
                raise ValueError(
                    f"residual_metric must have shape {(m, m)} "
                    f"(one row/col per constraint), got {w_res.shape}"
                )
            self.residual_metric = w_res
        else:
            self.residual_metric = None

        # W_state is dimensioned by the state vector n. Symmetry/definiteness
        # are validated here. The n x n shape is bound at construction when
        # state_dim, domain bounds, or state_metric make n available.
        if state_metric is not None:
            w_state = _validate_metric(state_metric, "state_metric", "pd")
            metric_dim = int(w_state.shape[0])
            if state_dim is not None and metric_dim != state_dim:
                raise ValueError(
                    f"state_metric dimension {metric_dim} does not match "
                    f"provided state_dim {state_dim}"
                )
            if domain_dim is not None and metric_dim != domain_dim:
                raise ValueError(
                    f"state_metric dimension {metric_dim} does not match "
                    f"domain dimension {domain_dim}"
                )
            self.state_metric = w_state
            inferred_state_dim = metric_dim
        else:
            self.state_metric = None
            inferred_state_dim = None

        declared_dims = [d for d in (state_dim, domain_dim, inferred_state_dim) if d is not None]
        if declared_dims and any(d != declared_dims[0] for d in declared_dims):
            raise ValueError(f"state dimension declarations disagree: {declared_dims}")
        self.state_dim = declared_dims[0] if declared_dims else None

    def _validate_state_vector(self, q: np.ndarray) -> np.ndarray:
        """
        Convert q to a finite 1-D vector and validate state dimension.

        The state dimension is checked only when state_dim was established at
        construction (directly, or inferred from domain bounds or state_metric).
        If no dimension was established, no dimension check is performed.
        """
        q = np.asarray(q, dtype=float)
        if q.ndim != 1:
            raise ValueError(f"state vector must be 1-D, got shape {q.shape}")
        if not np.all(np.isfinite(q)):
            raise ValueError("state vector must contain only finite values")
        if self.state_dim is not None and q.shape[0] != self.state_dim:
            raise ValueError(
                f"State dimension mismatch: expected {self.state_dim}, got {q.shape[0]}"
            )
        return q

    def _get_residuals(self, q: np.ndarray) -> np.ndarray:
        """
        Evaluate all holonomic constraint functions at q.

        Returns the residual vector epsilon, one entry per constraint. Each
        constraint c is expected to satisfy c(q) = 0 on the constraint manifold,
        so epsilon measures configuration-level constraint violation.
        """
        q = self._validate_state_vector(q)
        if not self.constraints:
            return np.zeros(0, dtype=float)
        epsilon = np.array([float(c(q)) for c in self.constraints], dtype=float)
        if not np.all(np.isfinite(epsilon)):
            raise ValueError("constraint residuals must contain only finite values")
        return epsilon

    def evaluate_holonomic_drift(self, current_state: np.ndarray) -> Tuple[np.ndarray, float]:
        """
        Evaluate constraint residuals and compute algebraic drift magnitude.

        If residual_metric is supplied, drift is computed as:
            D = sqrt(epsilon.T @ W_res @ epsilon)

        Otherwise, Euclidean residual norm is used.
        """
        epsilon = self._get_residuals(current_state)
        m = epsilon.shape[0]

        if self.residual_metric is not None:
            w_res = self.residual_metric
            if w_res.shape != (m, m):
                raise ValueError(f"residual_metric must have shape {(m, m)}, got {w_res.shape}")
            quad = float(epsilon.T @ w_res @ epsilon)
            drift_magnitude = float(np.sqrt(max(quad, 0.0)))
        else:
            drift_magnitude = float(np.linalg.norm(epsilon))

        return epsilon, drift_magnitude

    def compute_minimum_norm_correction(self, q_drifted: np.ndarray) -> CorrectionResult:
        """
        Iterative minimum-norm correction weighted by W_state.

        This attempts to reduce holonomic constraint residuals using local
        Jacobian correction. It does not claim global nearest-point projection
        or dynamic Riemannian manifold tracking.

        A corrected state is reported as "converged" only if:
          1. constraint residuals converge below tolerance
          2. coordinate/domain admissibility is verified at the converged state

        All outcomes, including failure modes, are reported through a
        CorrectionResult so the caller can distinguish numerical failure from
        domain rejection.
        """
        q = np.array(self._validate_state_vector(q_drifted), dtype=float, copy=True)
        n = q.shape[0]

        w_res = self.residual_metric
        w_state = self.state_metric

        if w_state is not None and w_state.shape != (n, n):
            raise ValueError(f"state_metric must have shape {(n, n)}, got {w_state.shape}")

        last_norm = float("nan")
        clamped_count = 0

        for iteration in range(1, self.max_iter + 1):
            try:
                epsilon = self._get_residuals(q)
            except ValueError as exc:
                return CorrectionResult(
                    status="non_finite",
                    state=None,
                    iterations=iteration,
                    residual_norm=last_norm,
                    clamped_steps=clamped_count,
                    message=f"invalid residual evaluation: {exc}",
                )

            m = epsilon.shape[0]

            if w_res is not None:
                quad = float(epsilon.T @ w_res @ epsilon)
                norm_val = float(np.sqrt(max(quad, 0.0)))
            else:
                norm_val = float(np.linalg.norm(epsilon))

            last_norm = norm_val

            if norm_val < self.tol:
                if self.domain.is_admissible(q):
                    return CorrectionResult(
                        status="converged",
                        state=q,
                        iterations=iteration,
                        residual_norm=norm_val,
                        clamped_steps=clamped_count,
                        message="residuals converged; state domain-admissible",
                    )
                return CorrectionResult(
                    status="converged_inadmissible",
                    state=None,
                    iterations=iteration,
                    residual_norm=norm_val,
                    clamped_steps=clamped_count,
                    message="residuals converged but state left the coordinate domain",
                )

            J = np.asarray(self.jacobian(q), dtype=float)
            if J.shape != (m, n):
                raise ValueError(f"Jacobian must have shape {(m, n)}, got {J.shape}")
            if not np.all(np.isfinite(J)):
                return CorrectionResult(
                    status="non_finite",
                    state=None,
                    iterations=iteration,
                    residual_norm=norm_val,
                    clamped_steps=clamped_count,
                    message="Jacobian contains non-finite values",
                )

            try:
                if w_state is not None:
                    # Metric-weighted minimum-norm correction:
                    # Minimize:  1/2 * delta.T @ W_state @ delta
                    # Subject:   J @ delta = epsilon
                    #
                    # delta = W_state^-1 @ J.T @ inv(J @ W_state^-1 @ J.T) @ epsilon
                    #
                    # Implemented with solve() instead of explicitly forming W_state^-1.
                    w_inv_jt = np.linalg.solve(w_state, J.T)
                    gram_matrix = J @ w_inv_jt
                    lambda_vec = np.linalg.solve(gram_matrix, epsilon)
                    delta = w_inv_jt @ lambda_vec
                else:
                    # Default Euclidean minimum-norm correction.
                    delta = np.linalg.pinv(J) @ epsilon

            except (np.linalg.LinAlgError, ValueError) as exc:
                return CorrectionResult(
                    status="linalg_failure",
                    state=None,
                    iterations=iteration,
                    residual_norm=norm_val,
                    clamped_steps=clamped_count,
                    message=f"linear-algebra step failed: {exc}",
                )

            if not np.all(np.isfinite(delta)):
                return CorrectionResult(
                    status="non_finite",
                    state=None,
                    iterations=iteration,
                    residual_norm=norm_val,
                    clamped_steps=clamped_count,
                    message="non-finite correction step",
                )

            if self.max_step_norm is not None:
                delta_norm = float(np.linalg.norm(delta))
                if delta_norm > self.max_step_norm:
                    delta = (delta / delta_norm) * self.max_step_norm
                    clamped_count += 1

            q = q - delta

            if not np.all(np.isfinite(q)):
                return CorrectionResult(
                    status="non_finite",
                    state=None,
                    iterations=iteration,
                    residual_norm=last_norm,
                    clamped_steps=clamped_count,
                    message="non-finite state after correction step",
                )

        return CorrectionResult(
            status="max_iterations",
            state=None,
            iterations=self.max_iter,
            residual_norm=last_norm,
            clamped_steps=clamped_count,
            message=f"did not converge within {self.max_iter} iterations",
        )
