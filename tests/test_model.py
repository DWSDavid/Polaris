from pathlib import Path

import pandas as pd

from src.research.model import derive_direction_weights, predict_proba, train_model


def test_requirements_include_scikit_learn():
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "scikit-learn" in requirements


def test_train_model_returns_oos_auc_and_feature_importance(tmp_path, monkeypatch):
    from src.research import model as research_model

    monkeypatch.setattr(research_model, "MODEL_CACHE_DIR", tmp_path)
    dataset = pd.DataFrame(
        {
            "week": list(range(1, 21)),
            "sector": ["A", "B"] * 10,
            "flow_strength": [0.9, 0.1, 0.8, 0.2, 0.85, 0.15, 0.7, 0.3, 0.95, 0.05] * 2,
            "trend_days": [8, 1, 7, 2, 8, 1, 6, 2, 9, 1] * 2,
            "label": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0] * 2,
        }
    )

    res = train_model(dataset, feature_cols=["flow_strength", "trend_days"], n_splits=3)

    assert set(res["feature_importance"]) == {"flow_strength", "trend_days"}
    assert "in_sample_auc" in res
    assert "out_sample_auc" in res
    assert "baseline_auc" in res
    assert 0 <= res["out_sample_auc"] <= 1
    assert (tmp_path / "direction_model.joblib").exists()

    probability = predict_proba(res["model"], {"flow_strength": 0.9, "trend_days": 8})
    assert 0 <= probability <= 1


def test_derive_direction_weights_normalizes_feature_importance():
    weights = derive_direction_weights({"flow_strength": 2.0, "trend_days": 1.0})

    assert weights["flow_strength"] == 2 / 3
    assert weights["trend_days"] == 1 / 3
