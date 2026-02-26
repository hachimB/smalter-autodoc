# src/smalter_autodoc/core/extractors/patterns/base_patterns.py
"""
Classe abstraite définissant l'interface des patterns
Chaque langue doit implémenter ces méthodes
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any
import re

class BasePatterns(ABC):
    """
    Interface pour patterns regex par langue
    
    Chaque langue doit fournir :
    - Patterns d'extraction (regex)
    - Mots-clés spécifiques à la langue
    - Formats de validation
    """
    
    # Métadonnées langue
    LANGUAGE_CODE: str = "xx"
    LANGUAGE_NAME: str = "Unknown"
    
    # ═════════════════════════════════════════════════════
    # PATTERNS COMMUNS (à surcharger si nécessaire)
    # ═════════════════════════════════════════════════════
    
    @property
    @abstractmethod
    def AMOUNT_PATTERN(self) -> str:
        """Pattern extraction montant (adapté au format local)"""
        pass
    
    @property
    @abstractmethod
    def DATE_PATTERNS(self) -> List[str]:
        """Liste patterns dates (formats locaux)"""
        pass
    
    # ═════════════════════════════════════════════════════
    # PATTERNS FACTURES
    # ═════════════════════════════════════════════════════
    
    @abstractmethod
    def get_invoice_number_patterns(self) -> List[str]:
        """Patterns numéro facture"""
        pass
    
    @abstractmethod
    def get_invoice_keywords(self) -> List[str]:
        """Mots-clés identifiant une facture (invoice, facture, فاتورة)"""
        pass
    
    @abstractmethod
    def get_supplier_patterns(self) -> List[str]:
        """Patterns extraction fournisseur"""
        pass
    
    @abstractmethod
    def get_ttc_patterns(self) -> List[str]:
        """Patterns montant TTC"""
        pass
    
    @abstractmethod
    def get_ht_patterns(self) -> List[str]:
        """Patterns montant HT"""
        pass
    
    @abstractmethod
    def get_vat_patterns(self) -> List[str]:
        """Patterns taux TVA"""
        pass
    
    # ═════════════════════════════════════════════════════
    # PATTERNS BANCAIRES
    # ═════════════════════════════════════════════════════
    
    @abstractmethod
    def get_iban_pattern(self) -> str:
        """Pattern IBAN (peut varier selon pays)"""
        pass
    
    @abstractmethod
    def get_balance_patterns(self) -> List[str]:
        """Patterns solde (balance, solde, رصيد)"""
        pass
    
    # ═════════════════════════════════════════════════════
    # MOTS À EXCLURE
    # ═════════════════════════════════════════════════════
    
    @abstractmethod
    def get_generic_words(self) -> List[str]:
        """Mots génériques à exclure (fournisseur, etc.)"""
        pass
    
    # ═════════════════════════════════════════════════════
    # VALIDATION FORMATS
    # ═════════════════════════════════════════════════════
    
    @abstractmethod
    def get_month_names(self) -> Dict[str, int]:
        """Mapping noms mois → numéro (janvier:1, january:1, يناير:1)"""
        pass
    
    @abstractmethod
    def get_valid_vat_rates(self) -> List[float]:
        """Taux TVA valides dans le pays (FR: 5.5, 10, 20)"""
        pass