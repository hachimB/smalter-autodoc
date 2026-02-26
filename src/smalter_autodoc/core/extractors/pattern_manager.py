# src/smalter_autodoc/core/extractors/pattern_manager.py
"""
Gestionnaire centralisé des patterns multi-langues
Auto-détection langue + fallback
"""

from typing import Optional, Dict, Type
import logging
from .patterns.base_patterns import BasePatterns
from .patterns.fr.invoice import FrenchInvoicePatterns
from .patterns.en.invoice import EnglishInvoicePatterns

logger = logging.getLogger(__name__)

class PatternManager:
    """
    Gère les patterns selon langue détectée
    
    Usage:
        manager = PatternManager(language='fr')
        patterns = manager.get_patterns()
        
        # Ou auto-détection
        manager = PatternManager.from_text(texte)
    """
    
    # Registre des langues disponibles
    AVAILABLE_LANGUAGES: Dict[str, Type[BasePatterns]] = {
        'fr': FrenchInvoicePatterns,
        'en': EnglishInvoicePatterns,
    }
    
    def __init__(self, language: str = 'fr'):
        """
        Args:
            language: Code langue ISO 639-1 (fr, en, ar, de, es...)
        """
        self.language = language.lower()
        
        if self.language not in self.AVAILABLE_LANGUAGES:
            logger.warning(
                f"Langue '{self.language}' non supportée. "
                f"Fallback sur 'fr'. "
                f"Langues disponibles: {list(self.AVAILABLE_LANGUAGES.keys())}"
            )
            self.language = 'fr'
        
        # Instancier patterns
        self.patterns: BasePatterns = self.AVAILABLE_LANGUAGES[self.language]()
        
        logger.info(f"PatternManager initialisé (langue: {self.patterns.LANGUAGE_NAME})")
    
    @classmethod
    def from_text(cls, text: str) -> 'PatternManager':
        """
        Auto-détection langue depuis texte
        
        Méthode simple : cherche mots-clés
        Plus sophistiqué : utiliser langdetect library
        """
        text_lower = text.lower()
        
        # Mots-clés discriminants
        if any(word in text_lower for word in ['facture', 'fournisseur', 'tva', 'siret']):
            return cls(language='fr')
        
        elif any(word in text_lower for word in ['invoice', 'supplier', 'vat', 'tax']):
            return cls(language='en')
        
        # Fallback français (Smalter est français)
        logger.info("Langue non détectée, fallback sur 'fr'")
        return cls(language='fr')
    
    def get_patterns(self) -> BasePatterns:
        """Retourne instance patterns de la langue"""
        return self.patterns
    
    @classmethod
    def list_available_languages(cls) -> Dict[str, str]:
        """Liste langues disponibles avec noms"""
        result = {}
        for code, pattern_class in cls.AVAILABLE_LANGUAGES.items():
            instance = pattern_class()
            result[code] = instance.LANGUAGE_NAME
        return result