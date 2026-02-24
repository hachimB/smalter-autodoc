# frontend/app.py
"""
Smalter AutoDoc - Interface de Démonstration
Pipeline OCR Intelligent avec 6 Portes de Validation
"""

import streamlit as st
import requests
from pathlib import Path
import json
from PIL import Image
import time
from datetime import datetime

# Configuration page
st.set_page_config(
    page_title="Smalter AutoDoc",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    /* Style global */
    .main {
        padding: 2rem;
    }
    
    /* Cards */
    .gate-card {
        background: white;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 5px solid #1f77b4;
    }
    
    .gate-card.success {
        border-left-color: #2ecc71;
    }
    
    .gate-card.rejected {
        border-left-color: #e74c3c;
    }
    
    .gate-card.pending {
        border-left-color: #f39c12;
    }
    
    /* Status badges */
    .status-badge {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    
    .status-success {
        background: #d4edda;
        color: #155724;
    }
    
    .status-rejected {
        background: #f8d7da;
        color: #721c24;
    }
    
    .status-pending {
        background: #fff3cd;
        color: #856404;
    }
    
    /* Metrics */
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
    }
    
    .metric-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    /* Timeline */
    .timeline {
        position: relative;
        padding-left: 30px;
    }
    
    .timeline::before {
        content: '';
        position: absolute;
        left: 10px;
        top: 0;
        bottom: 0;
        width: 2px;
        background: #ddd;
    }
    
    .timeline-item {
        position: relative;
        margin-bottom: 2rem;
    }
    
    .timeline-marker {
        position: absolute;
        left: -24px;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: #1f77b4;
        border: 3px solid white;
        box-shadow: 0 0 0 2px #1f77b4;
    }
    
    .timeline-marker.success {
        background: #2ecc71;
        box-shadow: 0 0 0 2px #2ecc71;
    }
    
    .timeline-marker.rejected {
        background: #e74c3c;
        box-shadow: 0 0 0 2px #e74c3c;
    }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
# CONFIGURATION API
# ══════════════════════════════════════════════════════════════

API_URL = "http://localhost:8000"

# ══════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════

if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'result' not in st.session_state:
    st.session_state.result = None

# ══════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════

st.title("🚀 Smalter AutoDoc")
st.markdown("### Pipeline OCR Intelligent avec Validation Multi-Portes")

st.markdown("---")

# ══════════════════════════════════════════════════════════════
# SIDEBAR - INFORMATIONS
# ══════════════════════════════════════════════════════════════

with st.sidebar:
    st.header("📊 Informations Système")
    
    # Check API status
    try:
        health_response = requests.get(f"{API_URL}/api/v1/health", timeout=2)
        if health_response.status_code == 200:
            st.success("✅ API Connectée")
        else:
            st.error("❌ API Erreur")
    except:
        st.error("❌ API Déconnectée")
    
    st.markdown("---")
    
    st.markdown("""
    ### Pipeline de Traitement
    
    **Porte 0** : Détection Type Fichier
    - PDF natif vs PDF scan vs Image
    
    **Porte 1** : Qualité Image
    - Netteté, Contraste, Résolution
    
    **Porte 2** : Extraction Texte
    - OCR Tesseract ou PyPDF2
    
    **Porte 3** : Validation Type Document
    - Vérification cohérence type
    
    **Porte 4** : Sélection Agent
    - InvoiceAgent, BankAgent, CashAgent
    
    **Porte 5** : Extraction Structurée
    - Regex + LLM hybride
    
    **Porte 6** : Validation Métier
    - Champs obligatoires présents
    """)
    
    st.markdown("---")
    
    st.info("""
    💡 **Conseil** : Utilisez des documents
    de bonne qualité (min 300 DPI) pour
    de meilleurs résultats.
    """)

# ══════════════════════════════════════════════════════════════
# SECTION UPLOAD
# ══════════════════════════════════════════════════════════════

col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📤 Upload Document")
    
    uploaded_file = st.file_uploader(
        "Sélectionnez un document",
        type=['pdf', 'png', 'jpg', 'jpeg'],
        help="Formats supportés : PDF, PNG, JPG"
    )
    
    if uploaded_file:
        st.success(f"✅ Fichier chargé : {uploaded_file.name}")
        
        # Preview si image
        if uploaded_file.type.startswith('image'):
            image = Image.open(uploaded_file)
            st.image(image, caption="Aperçu du document", use_container_width=True)

with col2:
    st.subheader("📋 Type de Document")
    
    document_type = st.selectbox(
        "Sélectionnez le type",
        options=["FACTURE", "RELEVE_BANCAIRE", "TICKET_Z", "DEVIS"],
        help="Choisissez le type de document que vous uploadez"
    )
    
    st.info(f"🏷️ Type sélectionné : **{document_type}**")

# ══════════════════════════════════════════════════════════════
# BOUTON TRAITEMENT
# ══════════════════════════════════════════════════════════════

st.markdown("---")

col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])

with col_btn1:
    process_button = st.button(
        "🚀 Lancer le Traitement",
        type="primary",
        disabled=uploaded_file is None,
        use_container_width=True
    )

with col_btn2:
    if st.session_state.processing_complete:
        if st.button("🔄 Nouveau Document", use_container_width=True):
            st.session_state.processing_complete = False
            st.session_state.result = None
            st.rerun()

# ══════════════════════════════════════════════════════════════
# TRAITEMENT
# ══════════════════════════════════════════════════════════════

if process_button and uploaded_file:
    
    # Reset
    st.session_state.processing_complete = False
    st.session_state.result = None
    
    # Placeholder pour animation
    progress_placeholder = st.empty()
    timeline_placeholder = st.empty()
    
    with progress_placeholder.container():
        st.markdown("### ⚙️ Traitement en cours...")
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    # Timeline container
    timeline_steps = []
    
    try:
        # Upload vers API
        uploaded_file.seek(0)
        files = {'file': (uploaded_file.name, uploaded_file, uploaded_file.type)}
        data = {'document_type': document_type}
        
        status_text.text("📤 Envoi du document...")
        progress_bar.progress(10)
        time.sleep(0.5)
        
        # Appel API
        status_text.text("🔄 Traitement par l'API...")
        progress_bar.progress(30)
        
        response = requests.post(
            f"{API_URL}/api/v1/upload",
            files=files,
            data=data,
            timeout=300
        )
        
        progress_bar.progress(90)
        
        if response.status_code == 200:
            result = response.json()
            st.session_state.result = result
            st.session_state.processing_complete = True
            
            progress_bar.progress(100)
            status_text.text("✅ Traitement terminé !")
            
            time.sleep(1)
            progress_placeholder.empty()
            
        else:
            st.error(f"❌ Erreur API : {response.status_code}")
            st.json(response.json())
    
    except Exception as e:
        progress_placeholder.empty()
        st.error(f"❌ Erreur : {str(e)}")

# ══════════════════════════════════════════════════════════════
# AFFICHAGE RÉSULTATS
# ══════════════════════════════════════════════════════════════

if st.session_state.processing_complete and st.session_state.result:
    
    result = st.session_state.result
    
    st.markdown("---")
    st.markdown("## 📊 Résultats du Traitement")
    
    # ══════════════════════════════════════════════════════
    # METRICS ROW
    # ══════════════════════════════════════════════════════
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        status = result.get('status', 'UNKNOWN')
        status_color = {
            'COMPLETED': '🟢',
            'REJECTED': '🔴',
            'PENDING': '🟡'
        }.get(status, '⚪')
        
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{status_color}</div>
            <div class="metric-label">Statut : {status}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        file_type = result.get('file_type', 'N/A')
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
            <div class="metric-value">📄</div>
            <div class="metric-label">{file_type}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        confidence = result.get('metadata', {}).get('agent', {}).get('confidence', 0)
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
            <div class="metric-value">{confidence}%</div>
            <div class="metric-label">Confiance</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        rejected_gate = result.get('rejected_at_gate')
        gate_text = f"Porte {rejected_gate}" if rejected_gate else "Toutes ✓"
        st.markdown(f"""
        <div class="metric-card" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
            <div class="metric-value">🚪</div>
            <div class="metric-label">{gate_text}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ══════════════════════════════════════════════════════
    # TIMELINE DES PORTES
    # ══════════════════════════════════════════════════════
    
    st.markdown("### 🚪 Pipeline de Validation")
    
    # Récupérer infos
    rejected_at = result.get('rejected_at_gate')
    metadata = result.get('metadata', {})
    quality_score = result.get('quality_score')
    
    gates_info = [
        {
            "number": 0,
            "name": "Détection Type Fichier",
            "status": "success",
            "details": f"Type détecté : {result.get('file_type')}",
            "metrics": metadata
        },
        {
            "number": 1,
            "name": "Validation Qualité Image",
            "status": "success" if not rejected_at or rejected_at > 1 else "rejected",
            "details": f"Score global : {quality_score.get('overall', 'N/A')}%" if quality_score else "Skippé (PDF natif)",
            "metrics": quality_score
        },
        {
            "number": 2,
            "name": "Extraction Texte (OCR)",
            "status": "success" if not rejected_at or rejected_at > 2 else "rejected",
            "details": f"Méthode : {metadata.get('text_extraction', {}).get('method', 'N/A')}",
            "metrics": metadata.get('text_extraction')
        },
        {
            "number": 3,
            "name": "Validation Type Document",
            "status": "success" if not rejected_at or rejected_at > 3 else "rejected",
            "details": metadata.get('type_validation', {}).get('reason', 'Validé') if 'type_validation' in metadata else "Validé",
            "metrics": metadata.get('type_validation')
        },
        {
            "number": 4,
            "name": "Sélection Agent",
            "status": "success" if not rejected_at or rejected_at > 4 else "rejected",
            "details": f"Agent : {metadata.get('agent', {}).get('name', 'N/A')}",
            "metrics": metadata.get('agent')
        },
        {
            "number": 5,
            "name": "Extraction Structurée",
            "status": "success" if result.get('status') == 'COMPLETED' else "rejected",
            "details": f"Méthode : {metadata.get('agent', {}).get('extraction_method', 'N/A')}",
            "metrics": result.get('extracted_data') if result.get('status') == 'COMPLETED' else None
        }
    ]
    
    # Afficher timeline
    st.markdown('<div class="timeline">', unsafe_allow_html=True)
    
    for gate in gates_info:
        
        if rejected_at and gate['number'] > rejected_at:
            continue  # Skip portes non atteintes
        
        status_class = gate['status']
        marker_class = f"timeline-marker {status_class}"
        
        st.markdown(f"""
        <div class="timeline-item">
            <div class="{marker_class}"></div>
            <div class="gate-card {status_class}">
                <h4>🚪 Porte {gate['number']} : {gate['name']}</h4>
                <p><strong>Statut :</strong> <span class="status-badge status-{status_class}">
                    {'✅ VALIDÉ' if status_class == 'success' else '❌ REJETÉ'}
                </span></p>
                <p>{gate['details']}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Expander pour détails
        if gate['metrics']:
            with st.expander(f"📋 Détails Porte {gate['number']}"):
                st.json(gate['metrics'])
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # ══════════════════════════════════════════════════════
    # DONNÉES EXTRAITES
    # ══════════════════════════════════════════════════════
    
    if result.get('status') == 'COMPLETED':
        
        st.markdown("---")
        st.markdown("### 📝 Données Extraites")
        
        extracted_data = metadata.get('extracted_data', {})
        
        if extracted_data:
            
            # Séparer champs trouvés / manquants
            missing_fields = extracted_data.get('_missing_fields', [])
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### ✅ Champs Trouvés")
                
                for key, value in extracted_data.items():
                    if not key.startswith('_') and key not in missing_fields:
                        # Formatage selon type
                        if isinstance(value, (int, float)):
                            display_value = f"**{value}**"
                        elif isinstance(value, list):
                            display_value = f"*{len(value)} éléments*"
                        else:
                            display_value = str(value)
                        
                        st.markdown(f"- **{key}** : {display_value}")
            
            with col2:
                st.markdown("#### ❌ Champs Manquants")
                
                if missing_fields:
                    for field in missing_fields:
                        st.markdown(f"- ⚠️ {field}")
                else:
                    st.success("Tous les champs ont été extraits !")
            
            # JSON complet
            with st.expander("🔍 Voir JSON Complet"):
                st.json(extracted_data)
    
    # ══════════════════════════════════════════════════════
    # REJET
    # ══════════════════════════════════════════════════════
    
    elif result.get('status') == 'REJECTED':
        
        st.markdown("---")
        st.error("### ❌ Document Rejeté")
        
        st.warning(f"**Raison** : {result.get('message')}")
        
        if result.get('suggestions'):
            st.markdown("#### 💡 Suggestions")
            for suggestion in result['suggestions']:
                st.info(suggestion)

# ══════════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════════

st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #888; padding: 2rem;'>
    <p>🚀 <strong>Smalter AutoDoc</strong> - Pipeline OCR Intelligent</p>
    <p>Développé avec FastAPI + Streamlit + Ollama</p>
    <p style='font-size: 0.8rem;'>PFE 2026 - Architecture Microservices</p>
</div>
""", unsafe_allow_html=True)