# src/smalter_autodoc/core/extractors/hybrid_extractor.py
"""
Orchestrateur Hybride : Combine Regex + LLM

Logique :
1. Regex extrait les champs structurés (rapide, précis)
2. LLM complète les champs manquants non-numériques
3. Merge avec priorité Regex sur LLM (montants jamais touchés par LLM)

Architecture optimisée :
- 80% des cas : Regex seul (0.1s)
- 20% des cas : Regex + LLM (2-5s)
"""

from typing import Dict, Any
from src.smalter_autodoc.core.extractors.regex_extractor import RegexExtractor
from src.smalter_autodoc.core.extractors.llm_extractor import LLMExtractor
import logging

logger = logging.getLogger(__name__)

class HybridExtractor:
    """
    Extraction hybride intelligente
    
    Principe :
    - Regex = First-class citizen (données critiques)
    - LLM = Complément sémantique (données textuelles)
    
    Garanties :
    - Les montants, SIRET, IBAN, dates viennent TOUJOURS du Regex
    - Le LLM ne peut PAS écraser ces valeurs
    - Si LLM échoue, Regex seul est suffisant
    
    Utilisation:
        >>> extractor = HybridExtractor()
        >>> result = extractor.extract(texte_ocr, "FACTURE")
        >>> print(result['_extraction_method'])
        'HYBRID'  # Ou 'REGEX' si LLM pas nécessaire
    """
    
    def __init__(self, use_llm: bool = True):
        """
        Args:
            use_llm: Si False, désactive LLM (Regex seul, mode fallback)
        """
        self.regex = RegexExtractor()
        self.llm = LLMExtractor() if use_llm else None
        
        logger.info(
            f"HybridExtractor initialisé "
            f"(LLM: {'activé' if use_llm else 'désactivé'})"
        )
    
    def extract(self, text: str, document_type: str) -> Dict[str, Any]:
        """
        Extraction complète : Regex → LLM si nécessaire → Merge
        
        Args:
            text: Texte brut OCR
            document_type: "FACTURE", "RELEVE_BANCAIRE", "TICKET_Z"
            
        Returns:
            Dict complet avec tous les champs disponibles
        """
        
        logger.info(f"═══ Extraction hybride : {document_type} ═══")
        
        # ══════════════════════════════════════════════════════
        # PHASE 1 : REGEX (Toujours exécuté)
        # ══════════════════════════════════════════════════════
        
        logger.info("Phase 1 : Extraction Regex...")
        
        if document_type == "FACTURE":
            regex_result = self.regex.extract_invoice_fields(text)
        elif document_type == "RELEVE_BANCAIRE":
            regex_result = self.regex.extract_bank_fields(text)
        else:
            logger.warning(f"Type document inconnu: {document_type}")
            regex_result = {
                "_missing_fields": [],
                "_extraction_method": "REGEX"
            }
        
        missing = regex_result.get("_missing_fields", [])
        
        logger.info(
            f"Phase 1 terminée : "
            f"{len([k for k in regex_result if not k.startswith('_')]) - len(missing)} champs trouvés, "
            f"{len(missing)} manquants → {missing}"
        )
        
        # ══════════════════════════════════════════════════════
        # PHASE 2 : LLM (Seulement si nécessaire ET disponible)
        # ══════════════════════════════════════════════════════
        
        llm_result = {}
        
        # Conditions pour utiliser le LLM :
        # 1. LLM activé (self.llm n'est pas None)
        # 2. Champs manquants non-numériques
        # 3. Ollama disponible
        
        if self.llm and missing:
            
            # Vérifier disponibilité Ollama
            if not self.llm.is_available():
                logger.warning(
                    "LLM non disponible (Ollama non lancé ?). "
                    "Poursuite avec Regex seul."
                )
            else:
                logger.info("Phase 2 : Extraction LLM...")
                
                try:
                    llm_result = self.llm.extract(text, missing, document_type)
                    
                    if llm_result:
                        logger.info(
                            f"Phase 2 terminée : "
                            f"{len(llm_result)} champs ajoutés par LLM → {list(llm_result.keys())}"
                        )
                    else:
                        logger.info("Phase 2 : LLM n'a extrait aucun champ supplémentaire")
                        
                except Exception as e:
                    logger.error(f"Erreur Phase 2 (LLM) : {e}", exc_info=True)
                    # Continue sans LLM
        
        elif not missing:
            logger.info("Phase 2 : Skippée (Regex a tout trouvé)")
        
        # ══════════════════════════════════════════════════════
        # MERGE : Regex prioritaire sur LLM
        # ══════════════════════════════════════════════════════
        
        logger.info("Merge Regex + LLM...")
        
        # Stratégie de merge :
        # 1. Commencer avec résultat LLM (champs textuels)
        # 2. Écraser TOUT avec résultat Regex (priorité absolue)
        
        final = {**llm_result}  # Copie LLM
        
        # Regex écrase tout (même si LLM a trouvé quelque chose)
        for key, value in regex_result.items():
            if not key.startswith('_'):  # Ignorer métadonnées
                if value is not None and value != [] and value != {}:
                    final[key] = value
        
        # ══════════════════════════════════════════════════════
        # MÉTADONNÉES FINALES
        # ══════════════════════════════════════════════════════
        
        # Recalculer champs manquants après merge
        final_missing = [
            k for k in regex_result.keys()
            if not k.startswith('_')
            and (final.get(k) is None or final.get(k) == [] or final.get(k) == {})
        ]
        
        final["_missing_fields"] = final_missing
        
        # Déterminer méthode d'extraction
        if llm_result:
            final["_extraction_method"] = "HYBRID"
        else:
            final["_extraction_method"] = "REGEX"
        
        logger.info(
            f"═══ Extraction terminée : {final['_extraction_method']} ═══\n"
            f"Résultat final : {len(final) - len(final_missing) - 2} champs complets, "
            f"{len(final_missing)} manquants"
        )
        
        return final