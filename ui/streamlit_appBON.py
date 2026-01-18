import streamlit as st
import requests

st.set_page_config(page_title="Prédiction Réussite Scolaire", page_icon="🎓", layout="wide")

st.title("🎓 Prédiction de la Réussite Scolaire")
st.markdown("**Le système choisit automatiquement le scénario S4/S3/S2 selon les notes G1/G2 saisies.**")
st.markdown("*✅ Interface conforme RGPD : aucune variable sensible collectée (sexe, adresse, situation familiale, profession des parents)*")

# URL de l'API
API_URL = st.sidebar.text_input("URL API", "http://api:8000")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Scénarios")
st.sidebar.markdown("""
- **S2** : G1 + G2 présents (Fiabilité : 92%)
- **S3** : G1 seul (Fiabilité : 87%)
- **S4** : Sans notes (Fiabilité : 80%)
""")

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔒 Conformité RGPD")
st.sidebar.markdown("""
Variables sensibles **exclues** :
- Sexe
- Adresse
- Taille famille
- Statut parental
- Profession parents
- Raison choix école
""")

# Formulaire principal
st.markdown("---")
st.markdown("## 📝 Informations de l'élève")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 👤 Profil")
    age = st.slider("Âge", 15, 22, 17)
    school = st.selectbox("École", ["GP", "MS"])
    guardian = st.selectbox("Tuteur", ["mother", "father", "other"])
    
    st.markdown("### 👨‍👩‍👧 Éducation parents")
    Medu = st.slider("Éducation mère (0-4)", 0, 4, 2, help="0=aucune, 4=supérieur")
    Fedu = st.slider("Éducation père (0-4)", 0, 4, 2, help="0=aucune, 4=supérieur")

with col2:
    st.markdown("### 🏫 Scolarité")
    traveltime = st.slider("Temps trajet (1-4)", 1, 4, 1, help="1=<15min, 4=>1h")
    studytime = st.slider("Temps étude/sem (1-4)", 1, 4, 2, help="1=<2h, 4=>10h")
    failures = st.slider("Échecs passés (0-4)", 0, 4, 0)
    schoolsup = st.selectbox("Soutien scolaire école", ["no", "yes"])
    famsup = st.selectbox("Soutien familial", ["no", "yes"])
    paid = st.selectbox("Cours payants (matière)", ["no", "yes"])

with col3:
    st.markdown("### 📚 Activités & Projets")
    activities = st.selectbox("Activités extra-scolaires", ["no", "yes"])
    nursery = st.selectbox("A fréquenté crèche", ["no", "yes"])
    higher = st.selectbox("Veut études supérieures", ["yes", "no"])
    internet = st.selectbox("Internet à la maison", ["yes", "no"])
    romantic = st.selectbox("Relation amoureuse", ["no", "yes"])

st.markdown("---")
col4, col5, col6 = st.columns(3)

with col4:
    st.markdown("### 🎯 Vie sociale")
    famrel = st.slider("Relation familiale (1-5)", 1, 5, 4, help="1=très mauvaise, 5=excellente")
    freetime = st.slider("Temps libre (1-5)", 1, 5, 3)
    goout = st.slider("Sorties avec amis (1-5)", 1, 5, 3)

with col5:
    st.markdown("### 🍷 Consommation alcool")
    Dalc = st.slider("Alcool en semaine (1-5)", 1, 5, 1, help="1=très faible, 5=très élevée")
    Walc = st.slider("Alcool week-end (1-5)", 1, 5, 1)

with col6:
    st.markdown("### 📈 Santé & Présence")
    health = st.slider("État de santé (1-5)", 1, 5, 3, help="1=très mauvais, 5=très bon")
    absences = st.number_input("Nombre d'absences", 0, 100, 0)

# Notes - Section séparée mise en évidence
st.markdown("---")
st.markdown("## 📊 Notes (optionnelles)")
st.markdown("*Laissez à 0 si la note n'est pas encore disponible. Le système adaptera automatiquement le scénario.*")

col_g1, col_g2, col_info = st.columns(3)

with col_g1:
    G1 = st.number_input("G1 - Moyenne Trimestre 1", 0, 20, 0, help="Note sur 20, 0 si inconnue")
    
with col_g2:
    G2 = st.number_input("G2 - Moyenne Trimestre 2", 0, 20, 0, help="Note sur 20, 0 si inconnue")

with col_info:
    st.markdown("### 🎯 Scénario prévu")
    if G1 > 0 and G2 > 0:
        st.success("**S2** - Fiabilité : 92%")
    elif G1 > 0:
        st.warning("**S3** - Fiabilité : 87%")
    else:
        st.info("**S4** - Fiabilité : 80%")

# Variable pour stocker si une prédiction vient d'être faite
prediction_made = False

# Bouton de prédiction
st.markdown("---")
if st.button("🔮 Prédire la réussite", type="primary", use_container_width=True):
    
    # Construire le payload (SANS variables sensibles)
    payload = {
        "school": school,
        "age": age,
        "Medu": Medu,
        "Fedu": Fedu,
        "guardian": guardian,
        "traveltime": traveltime,
        "studytime": studytime,
        "failures": failures,
        "schoolsup": schoolsup,
        "famsup": famsup,
        "paid": paid,
        "activities": activities,
        "nursery": nursery,
        "higher": higher,
        "internet": internet,
        "romantic": romantic,
        "famrel": famrel,
        "freetime": freetime,
        "goout": goout,
        "Dalc": Dalc,
        "Walc": Walc,
        "health": health,
        "absences": absences,
    }
    
    # Ajouter G1/G2 seulement si renseignés
    if G1 > 0:
        payload["G1"] = G1
    if G2 > 0:
        payload["G2"] = G2
    
    try:
        response = requests.post(
            f"{API_URL}/predict",
            json={"payload": payload, "session_id": "streamlit"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            prediction_made = True
            
            # Affichage du résultat
            st.markdown("---")
            st.markdown("## 📊 Résultat de la prédiction")
            
            col_res1, col_res2, col_res3 = st.columns(3)
            
            with col_res1:
                scenario = result.get("scenario", "?")
                st.metric("🎯 Scénario utilisé", scenario)
            
            with col_res2:
                pred = result.get("pred_label", 0)
                if pred == 1:
                    st.success("✅ RÉUSSITE PRÉDITE")
                else:
                    st.error("❌ RISQUE D'ÉCHEC")
            
            with col_res3:
                proba = result.get("pred_proba", 0)
                st.metric("📈 Probabilité réussite", f"{proba*100:.1f}%")
            
            # Détails
            latency = result.get("latency_ms", 0)
            st.caption(f"⏱️ Temps de réponse : {latency:.0f} ms")
            
        else:
            st.error(f"❌ Erreur API : {response.status_code}")
            st.code(response.text)
            
    except requests.exceptions.ConnectionError:
        st.error("❌ Impossible de se connecter à l'API. Vérifiez que l'API est lancée.")
    except Exception as e:
        st.error(f"❌ Erreur : {str(e)}")

# Section Upload et Réentraînement
st.markdown("---")
st.markdown("## 🔄 Mise à jour des données et réentraînement")

col_upload, col_train = st.columns(2)

with col_upload:
    st.markdown("### 📂 Charger de nouvelles données")
    uploaded_file = st.file_uploader(
        "Choisir un fichier CSV",
        type=["csv"],
        help="Le fichier doit contenir au minimum la colonne G3 (note finale)"
    )
    
    if uploaded_file is not None:
        if st.button("📤 Envoyer le fichier", use_container_width=True):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "text/csv")}
                response = requests.post(f"{API_URL}/upload-data", files=files, timeout=30)
                
                if response.status_code == 200:
                    result = response.json()
                    st.success(f"✅ Fichier uploadé : {result['rows']} lignes")
                    st.json({
                        "Réussite": result['success_distribution']['success'],
                        "Échec": result['success_distribution']['failure']
                    })
                else:
                    st.error(f"❌ Erreur : {response.text}")
            except Exception as e:
                st.error(f"❌ Erreur : {str(e)}")

with col_train:
    st.markdown("### 🤖 Réentraîner les modèles")
    st.markdown("*Après avoir uploadé de nouvelles données, cliquez pour réentraîner.*")
    
    if st.button("🔄 Réentraîner S2, S3, S4", use_container_width=True):
        try:
            with st.spinner("Entraînement en cours..."):
                response = requests.post(f"{API_URL}/train", timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                st.success(f"✅ Modèles réentraînés sur {result.get('n_samples', '?')} échantillons")
                
                # Afficher les résultats
                for scenario, metrics in result.get("models", {}).items():
                    acc = metrics.get("accuracy_cv", 0) * 100
                    f1 = metrics.get("f1_cv", 0) * 100
                    st.metric(f"{scenario}", f"Fiabilité : {acc:.1f}%", f"F1 : {f1:.1f}%")
            else:
                st.error(f"❌ Erreur : {response.text}")
        except Exception as e:
            st.error(f"❌ Erreur : {str(e)}")

# Footer - Historique (s'affiche automatiquement)
st.markdown("---")
st.markdown("### 📜 Historique des prédictions")

# Charger et afficher l'historique automatiquement
try:
    response = requests.get(f"{API_URL}/inferences?limit=10", timeout=5)
    if response.status_code == 200:
        data = response.json()
        inferences = data.get("inferences", [])
        if inferences:
            # Formater pour affichage
            df_display = []
            for inf in inferences:
                df_display.append({
                    "Date": inf.get("ts", "")[:19].replace("T", " "),
                    "Scénario": inf.get("scenario", ""),
                    "Prédiction": "✅ Réussite" if inf.get("pred_label") == 1 else "❌ Échec",
                    "Probabilité": f"{inf.get('pred_proba', 0)*100:.1f}%"
                })
            st.dataframe(df_display, use_container_width=True)
        else:
            st.info("Aucune prédiction enregistrée.")
    else:
        st.warning("Impossible de charger l'historique")
except Exception as e:
    st.warning(f"Historique non disponible : {e}")
