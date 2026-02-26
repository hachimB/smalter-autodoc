# src/smalter_autodoc/core/extractors/patterns/en/invoice.py
"""
English patterns for invoices
UK & US standards
"""

from ..base_patterns import BasePatterns
from typing import List, Dict

class EnglishInvoicePatterns(BasePatterns):
    
    LANGUAGE_CODE = "en"
    LANGUAGE_NAME = "English"

    
    @property
    def AMOUNT_PATTERN(self) -> str:
        """
        US/UK format: $30 or 30.00 or $1,234.56
        
        Accepte symbole $ AVANT et formats variés
        """
        return r'(?:[$£€]?\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\b'

    
    @property
    def DATE_PATTERNS(self) -> List[str]:
        return [
            r'\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b',  # MM/DD/YYYY (US)
            r'\b([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{2,4})\b',  # Month DD, YYYY
        ]
    

    
    def get_invoice_number_patterns(self) -> List[str]:
        return [
            # Pattern 1 : Avec mot-clé
            r'(?:invoice|inv\.?|no\.?|number|ref)\s*[:#]?\s*([A-Z0-9][\w\.\-/]*)',
            
            # Pattern 2 : Format structuré
            r'\b(INV[-/]?\d{2,8})\b',
            
            # Pattern 3 : Numérique pur (avec validation contexte)
            r'\b(\d{4,10})\b',
        ]
    
        
    def get_invoice_keywords(self) -> List[str]:
        return ['invoice', 'inv', 'inv.', 'no', 'no.', 'number', 'ref', 'reference']
    
    def get_supplier_patterns(self) -> List[str]:
        return [
            r'(?:supplier|vendor|from|seller)\s*[:=]?\s*([^\n\r]{3,80})',
            r'\b([A-Z][\w\s&]{2,50}(?:Ltd|LLC|Inc|Corp|Company))\b',
        ]
    
    
    def get_ttc_patterns(self) -> List[str]:
        return [
            # Pattern 1 : "Total" explicite
            r'(?:total|amount\s+due|balance\s+due)\s*[:\-]?\s*{amount}',
            
            # Pattern 2 : "Total including VAT"
            r'(?:total\s+including\s+(?:vat|tax))\s*[:\-]?\s*{amount}',
            
            # Pattern 3 : Juste "Total:" (US format)
            r'total\s*[:=]?\s*{amount}',
        ]


    def get_ht_patterns(self) -> List[str]:
        return [
            # Pattern 1 : "Subtotal" explicite
            r'(?:subtotal|sub-total|sub\s+total)\s*[:\-]?\s*{amount}',
            
            # Pattern 2 : "Net amount"
            r'(?:net\s+amount)\s*[:\-]?\s*{amount}',
        ]


    def get_vat_patterns(self) -> List[str]:
        return [
            r'(?:vat|v\.?a\.?t\.?|tax)\s*[:=]?\s*({rate})\s*%?',
        ]


    def get_iban_pattern(self) -> str:
        return r'(?:IBAN\s*[:=]?\s*)?([A-Z]{2}\d{2}\s*(?:[A-Z0-9\s]{12,30}))\b'
    
    def get_balance_patterns(self) -> List[str]:
        return [
            r'(?:balance|closing\s+balance|final\s+balance)\s*[:=]?\s*{amount}',
        ]
    
    def get_generic_words(self) -> List[str]:
        return [
            'invoice', 'quote', 'credit', 'note', 'proforma',
            'statement', 'receipt', 'page', 'date', 'total', 'customer'
        ]
    
    def get_month_names(self) -> Dict[str, int]:
        return {
            "january": 1, "jan": 1,
            "february": 2, "feb": 2,
            "march": 3, "mar": 3,
            "april": 4, "apr": 4,
            "may": 5,
            "june": 6, "jun": 6,
            "july": 7, "jul": 7,
            "august": 8, "aug": 8,
            "september": 9, "sep": 9, "sept": 9,
            "october": 10, "oct": 10,
            "november": 11, "nov": 11,
            "december": 12, "dec": 12,
        }
    
    def get_valid_vat_rates(self) -> List[float]:
        """UK VAT rates 2024"""
        return [0.0, 5.0, 20.0]  # Zero-rated, Reduced, Standard