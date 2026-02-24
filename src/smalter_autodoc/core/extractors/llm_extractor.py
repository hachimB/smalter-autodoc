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
    

    HARD_PROTECTED_FIELDS = {
        "montant_ttc", "montant_ht", "tva_rates",  # Montants = critique
        "siret", "siren", "iban", "bic",           # ID = critique
        "solde_initial", "solde_final",            # Banque = critique
    }

    SOFT_PROTECTED_FIELDS = {
        "numero_facture",  # Préférence Regex, mais LLM si échec
        "date_facture",    # Préférence Regex, mais LLM si échec
    }


    
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model: str = "mistral:7b-instruct-q4_0",
        timeout: int = 180
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
        document_type: str,
        field_hints: Dict[str, str] = None,
        allow_soft_protected: bool = True  # ← NOUVEAU
    ) -> Dict[str, Any]:
        """
        Args:
            allow_soft_protected: Si True, LLM peut extraire numero_facture/date
                                  en dernier recours (si Regex a échoué)
        """
        
        # Filtrer les champs
        fields_to_extract = []
        
        for field in missing_fields:
            # Ignorer champs internes
            if field.startswith('_'):
                continue
            
            # Bloquer champs HARD (jamais LLM)
            if field in self.HARD_PROTECTED_FIELDS:
                logger.debug(f"Champ {field} protégé (HARD), LLM skip")
                continue
            
            # Bloquer champs SOFT sauf si autorisé
            if field in self.SOFT_PROTECTED_FIELDS and not allow_soft_protected:
                logger.debug(f"Champ {field} protégé (SOFT), LLM skip")
                continue
            
            fields_to_extract.append(field)
        
        if not fields_to_extract:
            logger.info("Aucun champ éligible pour LLM")
            return {}
        
        logger.info(f"LLM va extraire : {fields_to_extract}")
        
        prompt = self._build_prompt(
            text, 
            fields_to_extract, 
            document_type,
            field_hints or {}  # ← Passer au prompt
        )
        
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
        document_type: str,
        field_hints: Dict[str, str]
    ) -> str:
        """Prompt minimaliste pour réduire temps génération"""
        
        # Tronquer agressivement
        text_truncated = text[:1500] if len(text) > 1500 else text
        
        # Liste champs SANS descriptions (plus court)
        fields_str = ", ".join([f'"{f}"' for f in fields])
        
        # Prompt ultra-court
        prompt = f"""Extrais ces champs en JSON strict (null si absent):
    Champs: {fields_str}

    Texte:
    {text_truncated}

    JSON:"""
        
        logger.debug(f"Prompt généré ({len(prompt)} chars)")
        
        return prompt
    


    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """Appelle Ollama (fix: meilleur logging + gestion erreurs)"""
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
                "num_predict": 200,  # ← Max token (plus rapide)
            }
        }
        
        logger.debug(f"Appel Ollama (modèle: {self.model})")
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            
            # ══════════════════════════════════════════════
            # VÉRIFIER STATUS HTTP
            # ══════════════════════════════════════════════
            
            if response.status_code != 200:
                logger.error(
                    f"Ollama HTTP {response.status_code}: {response.text[:200]}"
                )
                return None
            
            # ══════════════════════════════════════════════
            # PARSER RÉPONSE JSON
            # ══════════════════════════════════════════════
            
            data = response.json()
            
            # Vérifier erreur dans la réponse JSON
            if "error" in data:
                logger.error(f"Ollama erreur API: {data['error']}")
                return None
            
            # Extraire le texte généré
            llm_response = data.get("response")
            
            if llm_response is None:
                logger.error(f"Clé 'response' absente. Data reçu: {data}")
                return None
            
            if not llm_response.strip():
                logger.warning("Ollama a retourné une chaîne vide")
                return None
            
            # ══════════════════════════════════════════════
            # SUCCÈS - LOGGER LA RÉPONSE
            # ══════════════════════════════════════════════
            
            logger.info(
                f"✅ LLM réponse reçue ({len(llm_response)} chars): "
                f"{llm_response[:100]}..."
            )
            
            return llm_response
            
        except requests.exceptions.Timeout:
            logger.error(f"Timeout Ollama après {self.timeout}s")
            return None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur HTTP Ollama: {e}")
            return None
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON invalide d'Ollama: {e}")
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