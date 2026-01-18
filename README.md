# 🎓 Student Success Prediction

Prédiction de la réussite scolaire avec Machine Learning.

## 🚀 Démarrage rapide

### Docker Compose (recommandé)
```bash
docker-compose up -d
# API: http://localhost:8000
# UI:  http://localhost:8501
```

### Local
```bash
# API
pip install -r api/requirements.txt
uvicorn api.app:app --port 8000

# UI
pip install -r ui/requirements.txt
cd ui && streamlit run streamlit_app.py
```

## 📊 Scénarios
- **S2** : Avec G1+G2 (~92% accuracy)
- **S3** : Avec G1 seul (~85%)
- **S4** : Sans notes (~70%)
