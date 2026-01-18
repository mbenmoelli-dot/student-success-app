from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from pathlib import Path
import joblib
import pandas as pd
import sqlite3, json
from datetime import datetime
import time
import os
import shutil

APP_DIR = Path(__file__).parent
ROOT = APP_DIR.parent

# === Modèles multi-scénarios ===
MODELS = {
    "S2": ROOT / "models" / "model_s2.joblib",
    "S3": ROOT / "models" / "model_s3.joblib",
    "S4": ROOT / "models" / "model_s4.joblib",
}

# Variables par scénario (SANS variables sensibles)
SENSITIVE = ["sex", "address", "famsize", "Pstatus", "Mjob", "Fjob", "reason"]
SCENARIOS_CONFIG = {
    "S2": {"exclude": SENSITIVE + ["G3", "success"]},
    "S3": {"exclude": SENSITIVE + ["G3", "success", "G2"]},
    "S4": {"exclude": SENSITIVE + ["G3", "success", "G1", "G2"]},
}

FEATURE_TEMPLATE_PATH = ROOT / "models" / "feature_template.json"
DB_PATH = APP_DIR / "inferences.sqlite"
DATA_PATH = ROOT / "data" / "student_full.csv"

# MLflow tracking URI (sur le réseau Docker)
MLFLOW_TRACKING_URI = os.environ.get("MLFLOW_TRACKING_URI", "http://student-mlflow:5000")

# Charger le template de features
with open(FEATURE_TEMPLATE_PATH, "r") as f:
    FEATURE_TEMPLATE = json.load(f)

app = FastAPI(title="Student Success API", version="3.4.0")

# =========================
# Base de données
# =========================
def db_init():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS inferences ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "ts TEXT,"
        "session_id TEXT,"
        "scenario TEXT,"
        "input_json TEXT,"
        "pred_label INTEGER,"
        "pred_proba REAL)"
    )
    conn.commit()
    conn.close()

def db_log(payload: dict, label: int, proba: float, session_id: Optional[str], scenario: str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO inferences (ts, session_id, scenario, input_json, pred_label, pred_proba) VALUES (?, ?, ?, ?, ?, ?)",
        (datetime.utcnow().isoformat(), session_id, scenario, json.dumps(payload, ensure_ascii=False), int(label), float(proba))
    )
    conn.commit()
    conn.close()

def db_read(limit: int):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM inferences ORDER BY id DESC LIMIT ?",
        conn,
        params=(int(limit),)
    )
    conn.close()
    return df

# =========================
# Sélection du scénario
# =========================
def select_scenario(payload: dict) -> str:
    """
    Sélectionne le scénario en fonction de la PRÉSENCE de G1/G2 dans le payload.
    - G1 et G2 présents (même si = 0) → S2
    - G1 présent seul → S3
    - Aucun → S4
    
    Note: G2 sans G1 est considéré comme incohérent (traité comme S4)
    """
    has_g1 = "G1" in payload
    has_g2 = "G2" in payload
    
    # Cas incohérent : G2 sans G1 → on utilise S4
    if has_g2 and not has_g1:
        return "S4"
    
    if has_g1 and has_g2:
        return "S2"
    elif has_g1:
        return "S3"
    else:
        return "S4"

_loaded_models: Dict[str, Any] = {}

def get_model(scenario: str):
    if scenario not in MODELS:
        raise ValueError(f"Unknown scenario: {scenario}")
    if scenario not in _loaded_models:
        path = MODELS[scenario]
        if not path.exists():
            raise FileNotFoundError(f"Model missing for {scenario}: {path}")
        _loaded_models[scenario] = joblib.load(path)
    return _loaded_models[scenario]

class PredictIn(BaseModel):
    payload: Dict[str, Any] = Field(..., description="Features élève (G1/G2 optionnels)")
    session_id: Optional[str] = Field(None, description="ID session/utilisateur")

class PredictOut(BaseModel):
    scenario: str
    pred_label: int
    pred_proba: float
    latency_ms: float

@app.on_event("startup")
def startup():
    db_init()

@app.get("/health")
def health():
    return {
        "status": "ok",
        "models": {
            k: {"path": str(p), "exists": p.exists(), "loaded": (k in _loaded_models)}
            for k, p in MODELS.items()
        },
        "db_path": str(DB_PATH),
        "data_path": str(DATA_PATH),
        "data_exists": DATA_PATH.exists(),
        "mlflow_uri": MLFLOW_TRACKING_URI,
    }

@app.post("/predict", response_model=PredictOut)
def predict(inp: PredictIn):
    t0 = time.time()

    scenario = select_scenario(inp.payload)
    model = get_model(scenario)

    full_payload = FEATURE_TEMPLATE.copy()
    full_payload.update(inp.payload)
    
    for col in SCENARIOS_CONFIG[scenario]["exclude"]:
        full_payload.pop(col, None)

    try:
        X = pd.DataFrame([full_payload])
        proba = float(model.predict_proba(X)[0, 1])
        label = int(proba >= 0.5)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad input payload: {e}")

    latency_ms = (time.time() - t0) * 1000.0

    try:
        db_log(inp.payload, label, proba, inp.session_id, scenario)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Logging failure: {e}")

    return {"scenario": scenario, "pred_label": label, "pred_proba": proba, "latency_ms": float(latency_ms)}

@app.get("/inferences")
def inferences(limit: int = 50):
    try:
        df = db_read(limit)
        return {"inferences": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-data")
async def upload_data(file: UploadFile = File(...)):
    """
    Upload un nouveau fichier CSV pour remplacer les données d'entraînement.
    Le fichier doit contenir les colonnes nécessaires + G3 pour calculer 'success'.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Le fichier doit être un CSV")
    
    try:
        content = await file.read()
        temp_path = APP_DIR / "temp_upload.csv"
        with open(temp_path, "wb") as f:
            f.write(content)
        
        df = pd.read_csv(temp_path)
        
        required_cols = ["G3"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            temp_path.unlink()
            raise HTTPException(status_code=400, detail=f"Colonnes manquantes: {missing}")
        
        if "success" not in df.columns:
            df["success"] = (df["G3"] >= 10).astype(int)
        
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(DATA_PATH, index=False)
        temp_path.unlink()
        
        return {
            "status": "uploaded",
            "filename": file.filename,
            "rows": len(df),
            "columns": list(df.columns),
            "success_distribution": {
                "success": int(df["success"].sum()),
                "failure": int(len(df) - df["success"].sum())
            },
            "message": "Fichier uploadé. Appelez /train pour réentraîner les modèles."
        }
        
    except pd.errors.ParserError as e:
        raise HTTPException(status_code=400, detail=f"Erreur de parsing CSV: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur: {e}")

@app.post("/train")
def train():
    """
    Réentraîne les 3 modèles (S2, S3, S4) avec validation croisée.
    Log les métriques ET les modèles dans MLflow.
    """
    import numpy as np
    from sklearn.model_selection import StratifiedKFold, cross_validate
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    
    # Essayer d'importer MLflow
    mlflow_available = False
    mlflow = None
    try:
        import mlflow as mlflow_module
        mlflow = mlflow_module
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow_available = True
    except Exception:
        pass
    
    if not DATA_PATH.exists():
        raise HTTPException(status_code=500, detail="Training data missing. Upload data first with /upload-data")
    
    df = pd.read_csv(DATA_PATH)
    
    if "success" not in df.columns:
        if "G3" in df.columns:
            df["success"] = (df["G3"] >= 10).astype(int)
        else:
            raise HTTPException(status_code=500, detail="Colonne 'success' ou 'G3' manquante")
    
    y = df["success"]
    
    results = {}
    
    for scenario, config in SCENARIOS_CONFIG.items():
        features = [c for c in df.columns if c not in config["exclude"]]
        X = df[features]
        
        cat_cols = X.select_dtypes(include=["object"]).columns.tolist()
        num_cols = [c for c in X.columns if c not in cat_cols]
        
        pre = ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
            ("num", "passthrough", num_cols),
        ])
        
        pipe = Pipeline([("pre", pre), ("model", LogisticRegression(max_iter=2000))])
        
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        scores = cross_validate(pipe, X, y, cv=cv, scoring=["accuracy", "f1"])
        
        acc = float(np.mean(scores["test_accuracy"]))
        f1 = float(np.mean(scores["test_f1"]))
        
        pipe.fit(X, y)
        joblib.dump(pipe, MODELS[scenario])
        _loaded_models[scenario] = pipe
        
        # Log dans MLflow si disponible (métriques + modèle)
        mlflow_logged = False
        if mlflow_available and mlflow is not None:
            try:
                mlflow.set_experiment(f"student-success-{scenario}")
                with mlflow.start_run(run_name=f"{scenario}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"):
                    # Paramètres
                    mlflow.log_param("scenario", scenario)
                    mlflow.log_param("n_features", len(features))
                    mlflow.log_param("n_samples", len(df))
                    mlflow.log_param("model_type", "LogisticRegression")
                    mlflow.log_param("cv_folds", 5)
                    
                    # Métriques
                    mlflow.log_metric("accuracy_cv", acc)
                    mlflow.log_metric("f1_cv", f1)
                    
                    # Artifact : sauvegarder le modèle
                    mlflow.sklearn.log_model(pipe, artifact_path=f"model_{scenario}")
                    
                mlflow_logged = True
            except Exception as e:
                print(f"MLflow error for {scenario}: {e}")
                mlflow_logged = False
        
        results[scenario] = {
            "accuracy_cv": round(acc, 4),
            "f1_cv": round(f1, 4),
            "n_features": len(features),
            "mlflow_logged": mlflow_logged
        }
    
    return {
        "status": "trained",
        "n_samples": len(df),
        "models": results,
        "mlflow_tracking_uri": MLFLOW_TRACKING_URI if mlflow_available else "not available"
    }
