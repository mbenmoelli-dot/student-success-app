\
import mlflow
import mlflow.sklearn
import pandas as pd
import numpy as np

from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.linear_model import LogisticRegression
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

def build_pipeline(model, X):
    cat_cols = X.select_dtypes(include=["object"]).columns.tolist()
    num_cols = [c for c in X.columns if c not in cat_cols]
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
        ("num", "passthrough", num_cols),
    ])
    return Pipeline([("pre", pre), ("model", model)])

def main(data_csv="data/student_full.csv"):
    df = pd.read_csv(data_csv)
    y = df["success"]
    X = df.drop(columns=["success","G3"])

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    model = LogisticRegression(max_iter=2000)
    pipe = build_pipeline(model, X)

    with mlflow.start_run():
        scores = cross_validate(pipe, X, y, cv=cv, scoring=["accuracy","f1"])
        mlflow.log_metric("acc_mean", float(np.mean(scores["test_accuracy"])))
        mlflow.log_metric("f1_mean", float(np.mean(scores["test_f1"])))
        mlflow.log_param("model", "LogisticRegression")
        mlflow.log_param("cv", 5)

        pipe.fit(X, y)
        mlflow.sklearn.log_model(pipe, "model")

if __name__ == "__main__":
    main()
