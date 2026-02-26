"""
Agent de Base : Interface commune pour tous les agents

Chaque agent spécialisé hérite de cette classe et définit :
- document_type : Type de document géré
- required_fields : Champs obligatoires à extraire
- process() : Logique de traitement spécifique
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from pydantic import BaseModel
import logging
from src.smalter_autodoc.core.extractors.hybrid_extractor import HybridExtractor

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# MODÈLES DE DONNÉES
# ══════════════════════════════════════════════════════════════

class ProcessingResult(BaseModel):
    """
    Résultat du traitement d'un agent
    
    Structure unifiée pour tous les agents
    """
    success: bool
    document_type: str
    agent_name: str
    extracted_data: Dict[str, Any]
    missing_required_fields: List[str] = []
    extraction_method: str  # "REGEX", "LLM", "HYBRID"
    confidence_score: float = 0.0  # 0-100
    errors: List[str] = []
    warnings: List[str] = []

# ══════════════════════════════════════════════════════════════
# CLASSE DE BASE ABSTRAITE
# ══════════════════════════════════════════════════════════════

class BaseDocumentAgent(ABC):
    """
    Agent de base pour traitement de documents
    
    Responsabilités :
    1. Extraire les données (via HybridExtractor)
    2. Valider présence champs obligatoires
    3. Calculer score de confiance
    4. Retourner résultat structuré
    
    Chaque agent spécialisé définit :
    - document_type : Type de document
    - required_fields : Liste champs obligatoires
    - optional_fields : Liste champs optionnels
    """
    
    # À définir dans chaque agent
    document_type: str = "UNKNOWN"
    agent_name: str = "BaseAgent"
    
    # Champs obligatoires (agent rejette si manquants)
    required_fields: List[str] = []
    
    # Champs optionnels (bons à avoir mais non bloquants)
    optional_fields: List[str] = []

    # Hints pour guider le LLM
    field_hints: Dict[str, str] = {}
    
    def __init__(self, extractor: HybridExtractor = None):
        """
        Args:
            extractor: Instance HybridExtractor (avec langue configurée)
        """
        if extractor is None:
            extractor = HybridExtractor(use_llm=True, language='fr')
        
        self.extractor = extractor
        
        logger.info(
            f"{self.agent_name} initialisé "
            f"(langue: {self.extractor.regex.patterns.LANGUAGE_CODE})"
        )
    
    def process(self, text: str) -> ProcessingResult:
        """
        Traite un document et retourne le résultat structuré
        
        Workflow :
        1. Extraction (Regex + LLM)
        2. Validation champs obligatoires
        3. Calcul score de confiance
        4. Formatage résultat
        
        Args:
            text: Texte brut OCR du document
            
        Returns:
            ProcessingResult avec toutes les données extraites
        """
        
        logger.info(f"═══ {self.agent_name} : Traitement document ═══")
        
        try:
            # ══════════════════════════════════════════════════
            # ÉTAPE 1 : EXTRACTION
            # ══════════════════════════════════════════════════
            
            extracted = self.extractor.extract(text, self.document_type, field_hints=self.field_hints)
            
            # ══════════════════════════════════════════════════
            # ÉTAPE 2 : VALIDATION CHAMPS OBLIGATOIRES
            # ══════════════════════════════════════════════════
            
            missing_required = self._check_required_fields(extracted)
            
            success = len(missing_required) == 0
            
            if not success:
                logger.warning(
                    f"Champs obligatoires manquants : {missing_required}"
                )
            
            # ══════════════════════════════════════════════════
            # ÉTAPE 3 : CALCUL SCORE DE CONFIANCE
            # ══════════════════════════════════════════════════
            
            confidence = self._calculate_confidence(extracted)
            
            # ══════════════════════════════════════════════════
            # ÉTAPE 4 : WARNINGS (Champs optionnels manquants)
            # ══════════════════════════════════════════════════
            
            warnings = self._generate_warnings(extracted)
            
            # ══════════════════════════════════════════════════
            # RÉSULTAT FINAL
            # ══════════════════════════════════════════════════
            
            result = ProcessingResult(
                success=success,
                document_type=self.document_type,
                agent_name=self.agent_name,
                extracted_data=extracted,
                missing_required_fields=missing_required,
                extraction_method=extracted.get("_extraction_method", "UNKNOWN"),
                confidence_score=confidence,
                errors=[] if success else [
                    f"Champs obligatoires manquants : {', '.join(missing_required)}"
                ],
                warnings=warnings
            )
            
            logger.info(
                f"═══ {self.agent_name} : Terminé ═══\n"
                f"Succès: {success}, Confiance: {confidence:.1f}%"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur traitement {self.agent_name}: {e}", exc_info=True)
            
            return ProcessingResult(
                success=False,
                document_type=self.document_type,
                agent_name=self.agent_name,
                extracted_data={},
                missing_required_fields=self.required_fields,
                extraction_method="ERROR",
                confidence_score=0.0,
                errors=[f"Erreur fatale : {str(e)}"]
            )
    
    def _check_required_fields(self, data: Dict[str, Any]) -> List[str]:
        """
        Vérifie présence des champs obligatoires
        
        Returns:
            Liste des champs obligatoires manquants
        """
        missing = []
        
        for field in self.required_fields:
            value = data.get(field)
            
            # Considéré comme manquant si :
            # - None
            # - Chaîne vide
            # - Liste vide
            # - Dict vide
            if value is None or value == "" or value == [] or value == {}:
                missing.append(field)
        
        return missing
    
    def _calculate_confidence(self, data: Dict[str, Any]) -> float:
        """
        Calcule score de confiance basé sur :
        - Nombre de champs requis trouvés
        - Nombre de champs optionnels trouvés
        - Méthode d'extraction (Regex > LLM)
        
        Returns:
            Score 0-100
        """
        
        total_fields = len(self.required_fields) + len(self.optional_fields)
        
        if total_fields == 0:
            return 100.0  # Pas de champs définis = tout est OK
        
        # Compter champs trouvés
        found_required = len([
            f for f in self.required_fields
            if data.get(f) not in [None, "", [], {}]
        ])
        
        found_optional = len([
            f for f in self.optional_fields
            if data.get(f) not in [None, "", [], {}]
        ])
        
        # Pondération : requis = 70%, optionnels = 30%
        required_score = (found_required / len(self.required_fields)) * 70 if self.required_fields else 70
        optional_score = (found_optional / len(self.optional_fields)) * 30 if self.optional_fields else 30
        
        base_score = required_score + optional_score
        
        # Bonus si extraction Regex (plus fiable)
        method = data.get("_extraction_method", "UNKNOWN")
        if method == "REGEX":
            bonus = 5.0
        elif method == "HYBRID":
            bonus = 0.0
        else:
            bonus = -5.0
        
        final_score = min(100.0, max(0.0, base_score + bonus))
        
        return round(final_score, 2)
    
    def _generate_warnings(self, data: Dict[str, Any]) -> List[str]:
        """
        Génère warnings pour champs optionnels manquants
        
        Returns:
            Liste de messages d'avertissement
        """
        warnings = []
        
        for field in self.optional_fields:
            if data.get(field) in [None, "", [], {}]:
                warnings.append(
                    f"Champ optionnel manquant : {field} "
                    f"(non bloquant mais recommandé)"
                )
        
        return warnings