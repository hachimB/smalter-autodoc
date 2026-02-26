# src/smalter_autodoc/core/extractors/patterns/fr/invoice.py
"""
Patterns français pour factures
Standards France 2024-2026
"""

from ..base_patterns import BasePatterns
from typing import List, Dict

class FrenchInvoicePatterns(BasePatterns):
    
    LANGUAGE_CODE = "fr"
    LANGUAGE_NAME = "Français"
    
    # ═════════════════════════════════════════════════════
    # PATTERNS MONTANTS
    # ═════════════════════════════════════════════════════
    
    @property
    def AMOUNT_PATTERN(self) -> str:
        """Format français : 1 234,56 € ou 1.234,56"""
        return r'(?:(?:[\-−])?\s*(?:[€]|EUR)?\s*)?(\d{1,3}(?:[\s\.]?\d{3})*[.,]\d{1,2})\b'
    
    # ═════════════════════════════════════════════════════
    # PATTERNS DATES
    # ═════════════════════════════════════════════════════
    
    @property
    def DATE_PATTERNS(self) -> List[str]:
        return [
            r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b',  # DD/MM/YYYY
            r'\b(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})\b',    # YYYY-MM-DD
            r'\b(\d{1,2})\s*(janv\.?|f[ée]vr\.?|mars|avr\.?|mai|juin|juil\.?|ao[uû]t|sept\.?|oct\.?|nov\.?|d[ée]c\.?)\s*(\d{2,4})\b',
        ]
    
    # ═════════════════════════════════════════════════════
    # FACTURES
    # ═════════════════════════════════════════════════════
    

    def get_invoice_number_patterns(self) -> List[str]:
        return [
            # Pattern 1 : Avec mot-clé (PRIORITAIRE)
            r'(?:facture|fac\.?|n°|no\.?|num[eé]ro)\s*[:#]?\s*([A-Z0-9][\w\.\-/]*)',
            
            # Pattern 2 : Format structuré
            r'\b([A-Z]{1,6}[-/.]\d+(?:[-.]\d+)*)\b',
            
            # Pattern 3 : Alphanumérique classique
            r'\b([A-Z]{2,6}[-/]?\d{2,8})\b',
            
            # Pattern 4 : Numérique pur (DERNIER RECOURS, avec validation stricte)
            # → Sera validé dans _extract_invoice_number
            r'\b(\d{4,10})\b', 
        ]
    
    def get_invoice_keywords(self) -> List[str]:
        return [
            'facture', 'fac', 'fac.', 'n°', 'no', 'no.',
            'numéro', 'numero', 'ref', 'référence', 'reference'
        ]
    
    def get_supplier_patterns(self) -> List[str]:
        return [
            r'(?:fournisseur|vendeur|société|émetteur)\s*[:=]?\s*([^\n\r]{3,80})',
            r'\b([A-ZÀ-Ý][\w\s&]{2,50}(?:SARL|SAS|SA|EURL|SCI|SASU))\b',
            r'^([A-ZÀ-Ý][^\n\r]{3,70})$',

            r'(?:fournisseur|vendeur|société|company)\s*[:=]?\s*([^\n\r]{3,80})',
            
            # Chercher ligne avec forme juridique
            r'\b([A-ZÀ-Ý][\w\s&]{2,50}(?:SARL|SAS|SA|Ltd|LLC|Inc|Company|Compagnie))\b',

            r'^([A-ZÀ-Ý][^\n\r]{10,70})$',
        ]
    
    def get_ttc_patterns(self) -> List[str]:
        return [
            r'(?:total\s+)?ttc\s*[:=]?\s*{amount}',
            r'(?:net\s+[àa]\s+payer|à\s+régler)\s*[:=]?\s*{amount}',
            r'somme\s+[àa]\s+payer\s*[:=]?\s*{amount}',
            r'total\s+(?:g[ée]n[ée]ral)?\s*{amount}\s+{amount}',  # Tableau
        ]
    
    def get_ht_patterns(self) -> List[str]:
        return [
            r'(?:total\s+)?(?:h\.?t\.?|hors\s+taxes?)\s*[:=]?\s*{amount}',
            r'total\s+(?:g[ée]n[ée]ral)?\s*{amount}',
        ]
    
    def get_vat_patterns(self) -> List[str]:
        return [
            r'(?:tva|t\.?v\.?a\.?)\s*[:\-=]?\s*({rate})\s*%?',
        ]
    
    # ═════════════════════════════════════════════════════
    # BANCAIRE
    # ═════════════════════════════════════════════════════
    
    def get_iban_pattern(self) -> str:
        """IBAN français (FR + 25 caractères)"""
        return r'(?:IBAN\s*[:=]?\s*)?(FR\d{2}\s*(?:[A-Z0-9\s]{23}))\b'
    
    def get_balance_patterns(self) -> List[str]:
        return [
            r'(?:solde\s+final|nouveau\s+solde|solde\s+créditeur|solde\s+au)[\s\S]{0,50}?{amount}',
            r'solde\s*[:=]?\s*{amount}',
        ]
    
    # ═════════════════════════════════════════════════════
    # VALIDATION
    # ═════════════════════════════════════════════════════
    
    def get_generic_words(self) -> List[str]:
        return [
            'facture', 'invoice', 'devis', 'avoir', 'note', 'proforma',
            'relevé', 'extrait', 'bordereau', 'bon', 'ticket', 'reçu',
            'page', 'date', 'total', 'client', 'reference',
        ]
    def get_month_names(self) -> Dict[str, int]:
        return {
            "janvier": 1, "jan": 1, "janv": 1, "janv.": 1,
            "février": 2, "fevrier": 2, "fevr": 2, "fév": 2, "févr": 2,
            "mars": 3,
            "avril": 4, "avr": 4, "avr.": 4,
            "mai": 5,
            "juin": 6, "jun": 6,
            "juillet": 7, "juil": 7, "juil.": 7,
            "août": 8, "aout": 8, "aoû": 8,
            "septembre": 9, "sept": 9, "sep": 9,
            "octobre": 10, "oct": 10, "oct.": 10,
            "novembre": 11, "nov": 11, "nov.": 11,
            "décembre": 12, "decembre": 12, "dec": 12, "déc": 12,
        }
    
    def get_valid_vat_rates(self) -> List[float]:
        """Taux TVA français 2024-2026"""
        return [2.1, 5.5, 8.5, 10.0, 20.0]