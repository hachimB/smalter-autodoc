# src/smalter_autodoc/core/extractors/llm_extractor.py
"""
Phase 2 : Extraction par LLM Local (Ollama + Mistral 7B)

Rôle PRÉCIS :
- Complète SEULEMENT les champs que Regex n'a pas trouvés
- Ne touche PAS aux champs numériques critiques (montants, SIRET, dates)
- Comprend le contexte sémantique (noms, adresses, descriptions)

Modèle : Mistral 7B via Ollama (100% local, gratuit, sans GPU)
Vitesse : 2-5 secondes par document
"""

import json
import re
import requests
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class LLMExtractor:
    """
    Extraction sémantique via LLM local
    
    Principe :
    1. Reçoit texte + liste champs manquants (depuis Regex)
    2. Construit prompt ciblé (seulement les champs manquants)
    3. Appelle Ollama (HTTP local)
    4. Parse la réponse JSON
    5. Retourne seulement les champs non-numériques
    
    Utilisation:
        >>> extractor = LLMExtractor()
        >>> missing = ["fournisseur", "adresse_fournisseur", "conditions_paiement"]
        >>> result = extractor.extract(text, missing, "FACTURE")
        >>> print(result)
        {"fournisseur": "Carrefour Market", 
         "adresse_fournisseur": "123 Rue de Paris, 75001 Paris",
         "conditions_paiement": "30 jours fin de mois"}
    """
    
    # Champs qu'on NE confie JAMAIS au LLM
    # (trop critiques, risque d'hallucination)
    NUMERIC_PROTECTED_FIELDS = {
        "montant_ttc", "montant_ht", "tva_rates",
        "siret", "siren", "iban", "bic",
        "solde_initial", "solde_final",
        "numero_facture",  # Ajouté (pattern trop structuré pour LLM)
        "date_facture",    # Ajouté (format ISO strict)
    }
    
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "mistral",
        timeout: int = 30
    ):
        """
        Args:
            ollama_url: URL de l'API Ollama locale
            model: Nom du modèle (mistral, llama2, etc.)
            timeout: Timeout requête HTTP (secondes)
        """
        self.ollama_url = ollama_url
        self.model = model
        self.timeout = timeout
        
        logger.info(f"LLMExtractor initialisé (modèle: {model}, URL: {ollama_url})")
    
    def is_available(self) -> bool:
        """
        Vérifie qu'Ollama est accessible
        
        Returns:
            True si Ollama répond, False sinon
        """
        try:
            response = requests.get(
                f"{self.ollama_url}/api/tags",
                timeout=5
            )
            is_ok = response.status_code == 200
            
            if is_ok:
                logger.debug("Ollama disponible ✓")
            else:
                logger.warning(f"Ollama répond avec code {response.status_code}")
            
            return is_ok
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama non accessible: {e}")
            return False
    
    def extract(
        self,
        text: str,
        missing_fields: List[str],
        document_type: str
    ) -> Dict[str, Any]:
        """
        Extrait les champs manquants via LLM
        
        Args:
            text: Texte brut du document (OCR)
            missing_fields: Champs non trouvés par Regex
            document_type: "FACTURE", "RELEVE_BANCAIRE", "TICKET_Z"
            
        Returns:
            Dict avec champs extraits par LLM (seulement les non-numériques)
        """
        
        # ══════════════════════════════════════════════
        # FILTRER : Exclure champs numériques protégés
        # ══════════════════════════════════════════════
        
        # Retirer champs internes (commencent par _) et champs protégés
        fields_to_extract = [
            f for f in missing_fields
            if not f.startswith('_')
            and f not in self.NUMERIC_PROTECTED_FIELDS
        ]
        
        if not fields_to_extract:
            logger.info("Aucun champ éligible pour LLM (tous numériques ou déjà trouvés)")
            return {}
        
        logger.info(f"LLM va extraire : {fields_to_extract}")
        
        # ══════════════════════════════════════════════
        # CONSTRUIRE LE PROMPT
        # ══════════════════════════════════════════════
        
        prompt = self._build_prompt(text, fields_to_extract, document_type)
        
        # ══════════════════════════════════════════════
        # APPELER OLLAMA
        # ══════════════════════════════════════════════
        
        try:
            raw_response = self._call_ollama(prompt)
            
            if not raw_response:
                logger.warning("LLM n'a retourné aucune réponse")
                return {}
            
            # ══════════════════════════════════════════
            # PARSER LA RÉPONSE JSON
            # ══════════════════════════════════════════
            
            result = self._parse_json_response(raw_response)
            
            if result:
                logger.info(f"LLM a extrait : {list(result.keys())}")
            else:
                logger.warning("LLM n'a extrait aucun champ valide")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur LLM : {str(e)}", exc_info=True)
            return {}  # Échec silencieux → Regex seul suffit
    
    def _build_prompt(
        self,
        text: str,
        fields: List[str],
        document_type: str
    ) -> str:
        """
        Construit un prompt précis et minimaliste
        
        Principes :
        - Demander SEULEMENT les champs nécessaires
        - Forcer réponse JSON stricte
        - Interdire invention de données
        - Exemples concrets pour chaque type de champ
        """
        
        # Descriptions des champs pour guider le LLM
        field_descriptions = {
            "fournisseur": "nom complet de l'entreprise émettrice (ex: 'Carrefour Market SARL')",
            "adresse_fournisseur": "adresse complète de l'émetteur (rue, code postal, ville)",
            "client": "nom de l'entreprise destinataire",
            "adresse_client": "adresse complète du destinataire",
            "lignes_articles": "liste des produits/services (description, quantité, prix unitaire si présents)",
            "conditions_paiement": "conditions ou délai de paiement mentionné (ex: '30 jours fin de mois', 'paiement comptant')",
            "libelle": "description de l'opération bancaire",
        }
        
        # Construire la liste des champs demandés avec descriptions
        fields_list = "\n".join([
            f'- "{field}": {field_descriptions.get(field, field)}'
            for field in fields
        ])
        
        # Tronquer le texte si trop long (éviter overflow context window)
        # Mistral 7B context = 8k tokens ≈ 32k caractères
        text_truncated = text[:4000] if len(text) > 4000 else text
        
        prompt = f"""Tu es un assistant d'extraction de données pour documents comptables français.

Type de document : {document_type}

TEXTE DU DOCUMENT :
---
{text_truncated}
---

TÂCHE : Extrais UNIQUEMENT les champs suivants depuis le texte ci-dessus :
{fields_list}

RÈGLES STRICTES :
1. Réponds UNIQUEMENT avec un objet JSON valide, rien d'autre
2. Si un champ est absent du texte, mets null (pas d'invention)
3. Ne reformule pas, copie les valeurs exactes du texte
4. Pour les adresses : inclure rue, code postal et ville si présents
5. Pour les conditions de paiement : copier exactement la phrase mentionnée
6. Pas de commentaires, pas d'explication, juste le JSON

FORMAT RÉPONSE ATTENDU :
{{"field1": "valeur1", "field2": "valeur2", "field3": null}}

RÉPONSE JSON :"""
        
        return prompt
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """
        Appelle l'API Ollama en local
        
        Endpoint : POST /api/generate
        
        Returns:
            Texte brut de la réponse du LLM
        """
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,    # Réponse complète d'un coup (pas de streaming)
            "options": {
                "temperature": 0.1,   # Peu créatif = plus précis
                "top_p": 0.9,
                "num_predict": 500,   # Max tokens générés
            }
        }
        
        logger.debug(f"Appel Ollama (modèle: {self.model})")
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            data = response.json()
            llm_response = data.get("response", "")
            
            logger.debug(f"LLM réponse ({len(llm_response)} chars): {llm_response[:200]}...")
            
            return llm_response
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout Ollama après {self.timeout}s")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur requête Ollama: {e}")
            return None
    
    def _parse_json_response(self, raw: str) -> Dict[str, Any]:
        """
        Parse la réponse du LLM en JSON propre
        
        Gère les cas où le LLM ajoute du texte autour du JSON
        
        Args:
            raw: Réponse brute du LLM
            
        Returns:
            Dict Python avec les données extraites
        """
        
        # ══════════════════════════════════════════════
        # Chercher bloc JSON dans la réponse
        # ══════════════════════════════════════════════
        # (LLM ajoute parfois du texte avant/après)
        
        # Pattern pour trouver un objet JSON
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        
        if not json_match:
            logger.warning(f"Pas de JSON trouvé dans réponse LLM: {raw[:200]}")
            return {}
        
        json_str = json_match.group(0)
        
        # ══════════════════════════════════════════════
        # Parser le JSON
        # ══════════════════════════════════════════════
        
        try:
            result = json.loads(json_str)
            
            # Validation : doit être un dict
            if not isinstance(result, dict):
                logger.warning(f"LLM a retourné {type(result)} au lieu de dict")
                return {}
            
            # ══════════════════════════════════════════
            # Nettoyer : supprimer valeurs null/vides
            # ══════════════════════════════════════════
            
            cleaned = {
                k: v for k, v in result.items()
                if v is not None 
                and v != "" 
                and v != [] 
                and v != {}
            }
            
            logger.debug(f"JSON parsé avec succès: {list(cleaned.keys())}")
            
            return cleaned
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON invalide du LLM: {e}")
            logger.debug(f"JSON problématique: {json_str[:500]}")
            return {}