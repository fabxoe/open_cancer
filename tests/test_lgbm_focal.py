import numpy as np

from open_cancer.lgbm_focal import (
    make_sigmoid_focal_objective,
    reshape_multiclass_scores,
    softmax,
)


def test_reshape_multiclass_scores_accepts_fortran_flat_layout():
    matrix = np.arange(12, dtype=float).reshape(4, 3)
    flat = matrix.reshape(-1, order="F")
    assert np.array_equal(
        reshape_multiclass_scores(flat, rows=4, classes=3), matrix
    )


def test_softmax_is_row_normalized_and_argmax_preserving():
    scores = np.asarray([[1.0, 3.0, -2.0], [0.0, -1.0, 2.0]])
    probabilities = softmax(scores)
    assert np.allclose(probabilities.sum(axis=1), 1.0)
    assert np.array_equal(probabilities.argmax(axis=1), scores.argmax(axis=1))


def test_focal_gradient_matches_finite_difference():
    class Dataset:
        def get_label(self):
            return np.asarray([1], dtype=float)

    alpha = 0.25
    gamma = 1.0
    scores = np.asarray([[0.3, -0.2, 0.7]], dtype=float)
    objective = make_sigmoid_focal_objective(
        alpha=alpha, gamma=gamma, num_class=3
    )
    gradient, _ = objective(scores.copy(), Dataset())

    def loss(values):
        target = np.asarray([[0.0, 1.0, 0.0]])
        probability = 1.0 / (1.0 + np.exp(-values))
        true_probability = np.where(target == 1.0, probability, 1.0 - probability)
        true_alpha = np.where(target == 1.0, alpha, 1.0 - alpha)
        return float(
            np.sum(-true_alpha * (1.0 - true_probability) ** gamma * np.log(true_probability))
        )

    epsilon = 1e-6
    numerical = np.zeros_like(scores)
    for column in range(scores.shape[1]):
        upper = scores.copy()
        lower = scores.copy()
        upper[0, column] += epsilon
        lower[0, column] -= epsilon
        numerical[0, column] = (loss(upper) - loss(lower)) / (2.0 * epsilon)
    assert np.allclose(gradient, numerical, atol=1e-6, rtol=1e-6)
