"""
Tests for the Stability Engine v4.2 Integrity Unit holonomic drift scaffold.

Scope: exercises current scaffold behavior only. These tests do not assert
any architecture or system behavior beyond what the scaffold implements.

Run from the directory containing the scaffold module:

    pytest test_integrity_unit_v4_2.py
"""

import numpy as np
import pytest

from integrity_unit_v4_2 import (
    CoordinateDomain,
    IntegrityUnit,
    _validate_metric,
)


# --- Shared fixtures: a single holonomic constraint, the unit circle. ---
# c(q) = q0^2 + q1^2 - 1 = 0  on the constraint manifold.

def _unit_circle_constraint(q):
    return q[0] ** 2 + q[1] ** 2 - 1.0


def _unit_circle_jacobian(q):
    return np.array([[2.0 * q[0], 2.0 * q[1]]])


# --- Path 1: unweighted minimum-norm correction converges. ---

def test_unweighted_correction_converges():
    iu = IntegrityUnit([_unit_circle_constraint], _unit_circle_jacobian)

    epsilon, drift = iu.evaluate_holonomic_drift(np.array([1.5, 0.0]))
    assert drift == pytest.approx(1.25)
    assert epsilon.shape == (1,)

    result = iu.compute_minimum_norm_correction(np.array([1.5, 0.0]))
    assert result.status == "converged"
    assert result.ok is True
    assert result.state is not None
    assert result.state == pytest.approx(np.array([1.0, 0.0]), abs=1e-6)


# --- Path 2: metric-weighted correction (W_res and W_state) converges. ---

def test_weighted_correction_converges():
    iu = IntegrityUnit(
        [_unit_circle_constraint],
        _unit_circle_jacobian,
        residual_metric=np.array([[4.0]]),
        state_metric=np.diag([1.0, 3.0]),
    )

    result = iu.compute_minimum_norm_correction(np.array([0.0, 1.4]))
    assert result.status == "converged"
    assert result.state == pytest.approx(np.array([0.0, 1.0]), abs=1e-6)


# --- Path 3: residuals converge but the state leaves the domain. ---

def test_domain_rejection_returns_converged_inadmissible():
    # Box bounds require q0 >= 0.5; the correction settles near [0, 1].
    domain = CoordinateDomain(
        lower=np.array([0.5, -10.0]),
        upper=np.array([10.0, 10.0]),
    )
    iu = IntegrityUnit(
        [_unit_circle_constraint],
        _unit_circle_jacobian,
        domain=domain,
    )

    result = iu.compute_minimum_norm_correction(np.array([0.0, 1.4]))
    assert result.status == "converged_inadmissible"
    assert result.state is None
    assert result.ok is False


# --- Path 4: metric validation rejects invalid metric matrices. ---

@pytest.mark.parametrize(
    "matrix, definiteness, reason",
    [
        (np.array([[1.0, 2.0], [0.0, 1.0]]), "pd", "non-symmetric"),
        (np.array([[-1.0]]), "pd", "non-positive-definite"),
        (np.array([[-1.0]]), "psd", "non-positive-semidefinite"),
    ],
)
def test_metric_validation_rejects_invalid(matrix, definiteness, reason):
    with pytest.raises(ValueError):
        _validate_metric(matrix, reason, definiteness)


# --- Path 5: iteration budget exhausted on an unsatisfiable constraint. ---

def test_max_iterations_when_unsatisfiable():
    # c(q) = q0^2 + 1 has no real root, so residuals never reach tolerance.
    iu = IntegrityUnit(
        [lambda q: q[0] ** 2 + 1.0],
        lambda q: np.array([[2.0 * q[0]]]),
        max_iterations=5,
    )

    result = iu.compute_minimum_norm_correction(np.array([1.0]))
    assert result.status == "max_iterations"
    assert result.iterations == 5
    assert result.state is None
