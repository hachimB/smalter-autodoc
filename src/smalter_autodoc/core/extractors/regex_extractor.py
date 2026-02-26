# src/smalter_autodoc/core/extractors/regex_extractor.py
"""
Extractor refactorisé avec patterns configurables
"""

import re
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from .pattern_manager import PatternManager
from .patterns.base_patterns import BasePatterns

logger = logging.getLogger(__name__)

class RegexExtractor:
    """
    Extracteur regex multi-langues
    
    Usage:
        # Langue explicite
        extractor = RegexExtractor(language='fr')
        
        # Auto-détection
        extractor = RegexExtractor.from_text(texte)
    """
    

    def _normalize_text(self, text: str) -> str:
        """
        Normalise le texte pour faciliter l'extraction
        
        Corrections :
        - Supprimer indentations excessives
        - Normaliser espaces multiples
        - Garder la structure (sauts de ligne)
        """
        lines = []
        for line in text.split('\n'):
            # Supprimer indentation mais garder la ligne
            cleaned = line.strip()
            if cleaned:  # Ignorer lignes vides
                lines.append(cleaned)
        
        return '\n'.join(lines)
    


    def __init__(self, language: str = 'fr'):
        """
        Args:
            language: Code langue (fr, en, ar...)
        """
        self.pattern_manager = PatternManager(language=language)
        self.patterns: BasePatterns = self.pattern_manager.get_patterns()
        
        logger.info(
            f"RegexExtractor initialisé "
            f"(langue: {self.patterns.LANGUAGE_NAME})"
        )
    
    @classmethod
    def from_text(cls, text: str) -> 'RegexExtractor':
        """Factory avec auto-détection langue"""
        manager = PatternManager.from_text(text)
        extractor = cls.__new__(cls)
        extractor.pattern_manager = manager
        extractor.patterns = manager.get_patterns()
        return extractor
    
    def extract_invoice_fields(self, text: str) -> Dict[str, Any]:
        """Extraction facture (patterns adaptés à la langue)"""
        
        text = self._normalize_text(text)
        
        result = {
            "numero_facture": None,
            "date_facture": None,
            "montant_ttc": None,
            "montant_ht": None,
            "tva_rates": [],
            "fournisseur": None,
            "siret": None,
            "adresse_fournisseur": None,
            "lignes_articles": [],
            "conditions_paiement": None,
            "_missing_fields": [],
            "_extraction_method": "REGEX",
            "_language": self.patterns.LANGUAGE_CODE, 
        }
        
        # Extraction avec patterns langue
        result["numero_facture"] = self._extract_invoice_number(text)
        result["date_facture"] = self._extract_date(text)
        result["montant_ttc"] = self._extract_ttc(text)
        result["montant_ht"] = self._extract_ht(text)
        result["tva_rates"] = self._extract_vat_rates(text)
        result["fournisseur"] = self._extract_supplier(text)
        result["siret"] = self._extract_siret(text) if self.patterns.LANGUAGE_CODE == 'fr' else None
        
        # Tracking
        missing = [k for k, v in result.items() 
                   if not k.startswith('_') and (v is None or v == [])]
        result["_missing_fields"] = missing
        
        logger.info(
            f"Regex ({self.patterns.LANGUAGE_CODE}) → "
            f"{len(result) - len(missing) - 3}/{len(result) - 3} champs"
        )
        
        return result
    
    # ═══════════════════════════════════════════════════════
    # MÉTHODES D'EXTRACTION (utilisent self.patterns)
    # ═══════════════════════════════════════════════════════
    
    def _extract_invoice_number(self, text: str) -> Optional[str]:
        """Extraction numéro avec patterns langue"""
        patterns = self.patterns.get_invoice_number_patterns()
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                
                # Validation 1 : Mots communs
                if val.lower() in self.patterns.get_generic_words():
                    continue
                
                # Validation 2 : Longueur minimum
                if len(val) < 1:
                    continue
                
                # Validation 3 : Rejeter "to", "in", "no" seuls
                if len(val) <= 2 and val.lower() in ['to', 'in', 'no', 'by', 'or']:
                    logger.debug(f"Rejet mot anglais court: {val}")
                    continue
                
                # Validation 4 : Rejeter si ressemble à téléphone
                if len(val) == 10 and val.isdigit():
                    context = text[max(0, m.start()-50):m.start()+50]
                    if 'invoice' not in context.lower() and 'number' not in context.lower():
                        logger.debug(f"Rejet téléphone suspect: {val}")
                        continue
                
                logger.debug(f"✅ Numéro facture: {val}")
                return val
        
        return None

    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extraction date avec patterns + mois langue"""
        patterns = self.patterns.DATE_PATTERNS
        months = self.patterns.get_month_names()
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if not m:
                continue
            
            groups = m.groups()
            
            try:
                # Logique extraction (similaire à avant)
                # Mais utilise months mapping de la langue
                
                # Si groupe contient nom mois
                for i, g in enumerate(groups):
                    if isinstance(g, str) and g.replace('.','').lower() in months:
                        month_name = g.replace('.','').lower()
                        month = months[month_name]
                        
                        # Extraire jour et année
                        day = int(groups[i-1] if i > 0 else groups[i+1])
                        year = int(groups[i+1] if i < len(groups)-1 else groups[i-1])
                        
                        if year < 100:
                            year += 2000 if year <= 50 else 1900
                        
                        dt = datetime(year, month, day)
                        return dt.strftime("%Y-%m-%d")
                
                # Format numérique standard
                if len(groups[0]) == 4:  # YYYY-MM-DD
                    year, month, day = map(int, groups)
                else:  # DD/MM/YYYY
                    day, month, year = map(int, groups)
                
                if year < 100:
                    year += 2000 if year <= 50 else 1900
                
                dt = datetime(year, month, day)
                return dt.strftime("%Y-%m-%d")
                
            except (ValueError, KeyError):
                continue
        
        return None
    
    def _extract_ttc(self, text: str) -> Optional[float]:
        """Extraction TTC avec patterns langue"""
        patterns = self.patterns.get_ttc_patterns()
        amount_pattern = self.patterns.AMOUNT_PATTERN
        
        amounts = []
        for pat in patterns:
            # Remplacer {amount} par pattern réel
            full_pattern = pat.replace('{amount}', amount_pattern)
            
            for m in re.finditer(full_pattern, text, re.IGNORECASE):
                amt = self._parse_amount(m.group(m.lastindex if m.lastindex else 1))
                if amt:
                    amounts.append(amt)
        
        return max(amounts) if amounts else None
    

    def _extract_ht(self, text: str) -> Optional[float]:
        """Extraction HT avec patterns langue"""
        patterns = self.patterns.get_ht_patterns()
        amount_pattern = self.patterns.AMOUNT_PATTERN
        
        for pat in patterns:
            full_pattern = pat.replace('{amount}', amount_pattern)
            m = re.search(full_pattern, text, re.IGNORECASE)
            if m:
                amt = self._parse_amount(m.group(1))
                if amt:
                    return amt
        
        return None
    

    def _extract_vat_rates(self, text: str) -> List[float]:
        """Extraction taux TVA validés selon pays"""
        patterns = self.patterns.get_vat_patterns()
        valid_rates = self.patterns.get_valid_vat_rates()
        
        rates = set()
        for pat in patterns:
            # Construire pattern avec taux valides
            rate_regex = '|'.join([str(r).replace('.', '[.,]') for r in valid_rates])
            full_pattern = pat.replace('{rate}', f'({rate_regex})')
            
            for m in re.finditer(full_pattern, text, re.IGNORECASE):
                rate = float(m.group(1).replace(',', '.'))
                if rate in valid_rates:
                    rates.add(rate)
        
        return sorted(rates)
    

    def _extract_supplier(self, text: str) -> Optional[str]:
        """Extraction fournisseur avec patterns langue"""
        patterns = self.patterns.get_supplier_patterns()
        generic_words = self.patterns.get_generic_words()
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if not m:
                continue
            
            candidate = m.group(1).strip()
            
            # Validation
            if any(word in candidate.lower() for word in generic_words):
                continue
            
            if candidate.replace(' ', '').isdigit():
                continue
            
            words = [w for w in candidate.split() if len(w) > 2]
            if len(words) >= 2:
                return candidate
        
        return None

    def extract_bank_fields(self, text: str) -> Dict[str, Any]:
        """Extrait les champs clés d'un relevé bancaire"""
        
        text = self._normalize_text(text)
        
        result: Dict[str, Any] = {
            "iban": None,
            "bic": None,
            "solde_initial": None,
            "solde_final": None,
            "transactions": [],
            "_missing_fields": [],
            "_extraction_method": "REGEX",
            "_language": self.patterns.LANGUAGE_CODE,
        }

        result["iban"] = self._extract_iban(text)
        result["bic"] = self._extract_bic(text)
        result["solde_final"] = self._extract_solde(text)

        missing = [k for k, v in result.items() 
                if not k.startswith('_') and (v is None or v == [])]
        result["_missing_fields"] = missing

        logger.info(
            f"Regex ({self.patterns.LANGUAGE_CODE}) relevé bancaire → "
            f"{len(result) - len(missing) - 3}/{len(result) - 3} champs"
        )

        return result

    # ══════════════════════════════════════════════════════════════
    # MÉTHODES BANCAIRES ( avec self.patterns)
    # ══════════════════════════════════════════════════════════════

    def _extract_iban(self, text: str) -> Optional[str]:
        """Extraction IBAN avec pattern langue"""
        pattern = self.patterns.get_iban_pattern()  # ← Utiliser pattern langue
        
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return None
        
        # Nettoyer
        iban = re.sub(r'\s', '', m.group(1)).upper()
        
        # Validation longueur
        valid_lengths = {
            'FR': 27, 'DE': 22, 'ES': 24, 'IT': 27, 'PT': 25,
            'BE': 16, 'NL': 18, 'LU': 20, 'CH': 21, 'GB': 22,
            'IE': 22, 'AT': 20, 'PL': 28, 'SE': 24, 'DK': 18,
        }
        
        country_code = iban[:2]
        expected_length = valid_lengths.get(country_code)
        
        if expected_length and len(iban) == expected_length:
            logger.debug(f"IBAN valide ({country_code}): {iban[:8]}...")
            return iban
        
        return None

    def _extract_bic(self, text: str) -> Optional[str]:
        """BIC/SWIFT (8 ou 11 caractères)"""
        pattern = r'(?:BIC|SWIFT)\s*[:=]?\s*([A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?)\b'
        m = re.search(pattern, text, re.IGNORECASE)
        
        if m:
            bic = m.group(1).strip().upper()
            logger.debug(f"BIC trouvé: {bic}")
            return bic
        
        return None

    def _extract_solde(self, text: str) -> Optional[float]:
        """Solde final avec patterns langue"""
        patterns = self.patterns.get_balance_patterns()  # ← Pattern langue
        amount_pattern = self.patterns.AMOUNT_PATTERN     # ← Pattern langue
        
        amounts = []
        for pat in patterns:
            # Remplacer placeholder {amount} par pattern réel
            full_pattern = pat.replace('{amount}', amount_pattern)
            
            for m in re.finditer(full_pattern, text, re.IGNORECASE):
                amount_str = m.group(m.lastindex) if m.lastindex else m.group(1)
                amt = self._parse_amount(amount_str)
                if amt is not None:
                    amounts.append(amt)
        
        if amounts:
            value = amounts[-1]  # Prendre le dernier (généralement solde final)
            logger.debug(f"Solde final trouvé: {value}€")
            return value
        
        return None

    def _extract_siret(self, text: str) -> Optional[str]:
        """
        SIRET français uniquement
        Ne s'applique QUE si langue = 'fr'
        """
        
        # Skip si pas français
        if self.patterns.LANGUAGE_CODE != 'fr':
            return None
        
        patterns = [
            r'\bSIRET\b\s*(?:n°|num[eé]ro)?\s*[:\-]?\s*([\d\s]{14,20})',
            r'(?:siret|siren)\s*[:=]?\s*(\d[\d\s]{12,18}\d)',
            r'\b(\d{3}\s+\d{3}\s+\d{3}\s+\d{5})\b',
        ]
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if not m:
                continue
            
            cleaned = re.sub(r'\s', '', m.group(1))
            
            if len(cleaned) == 14 and cleaned.isdigit():
                if self._validate_siret_luhn(cleaned):
                    logger.debug(f"SIRET: {cleaned}")
                    return cleaned
        
        return None



    def _validate_siret_luhn(self, siret: str) -> bool:
        """
        Validation Luhn adaptée pour SIRET français
        
        Algorithme :
        1. Pour chaque chiffre en position paire (0, 2, 4...), doubler
        2. Si résultat > 9, soustraire 9
        3. Somme totale doit être multiple de 10
        
        Exemple : 732 829 320 00074
        Position : 0  1  2  3  4  5  6  7  8  9 10 11 12 13
        Chiffre  : 7  3  2  8  2  9  3  2  0  0  0  0  7  4
        Double   : 14 3  4  8  4  9  6  2  0  0  0  0  14 4
        Ajusté   : 5  3  4  8  4  9  6  2  0  0  0  0  5  4
        Somme    : 50 → 50 % 10 = 0 ✅
        """
        total = 0
        for i, digit in enumerate(siret):
            d = int(digit)
            if i % 2 == 0:  # Positions paires (0-indexed)
                d *= 2
                if d > 9:
                    d -= 9
            total += d
        
        return total % 10 == 0

    # ────────────────────────────────────────────────
    # UTILITAIRE : NETTOYAGE MONTANT
    # ────────────────────────────────────────────────

    def _parse_amount(self, s: str) -> Optional[float]:
        """
        Convertit string montant en float
        
        Gère :
        - Formats internationaux : 1.234,56 (FR) / 1,234.56 (EN) / 1'234.56 (CH)
        - Erreurs OCR : O→0, l→1, I→1, S→5
        - Montants négatifs : -120,50 (avoirs)
        - Devises multiples : €, $, £, CHF, USD, EUR
        
        Exemples :
        "1 234,56 €"   → 1234.56
        "1.234,56"     → 1234.56
        "1,234.56"     → 1234.56
        "1'234.56"     → 1234.56
        "1O8,4O"       → 108.40 (corrections OCR)
        "-120,50"      → -120.50
        """
        if not s or not s.strip():
            return None

        cleaned = s.strip()

        # ── Corrections OCR courantes ──
        cleaned = cleaned.replace('O', '0').replace('o', '0')  # O lettre → 0 chiffre
        cleaned = cleaned.replace('l', '1').replace('I', '1')  # l ou I → 1
        cleaned = cleaned.replace('S', '5').replace('Z', '2')  # Moins fréquent

        # ── Supprimer devises et espaces inutiles ──
        cleaned = re.sub(r'[€$£]|CHF|EUR|USD|FCFA|XOF|GBP|MAD', '', cleaned)
        cleaned = re.sub(r'\s', '', cleaned)
        
        # ── Apostrophe suisse ──
        cleaned = cleaned.replace("'", "")

        # ── Détecter et normaliser le format décimal ──
        # Format européen : 1.234,56 (point = milliers, virgule = décimal)
        if re.match(r'^\-?\d{1,3}(\.\d{3})+(,\d{1,2})?$', cleaned):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        
        # Format anglo-saxon : 1,234.56 (virgule = milliers, point = décimal)
        elif re.match(r'^\-?\d{1,3}(,\d{3})+(\.\d{1,2})?$', cleaned):
            cleaned = cleaned.replace(',', '')
        
        # Format simple : 1234,56 ou 1234.56
        else:
            cleaned = cleaned.replace(',', '.')

        # ── Conversion finale ──
        try:
            value = float(cleaned)
            return value
        except ValueError:
            logger.warning(f"Échec parsing montant: '{s}' → '{cleaned}'")
            return None
