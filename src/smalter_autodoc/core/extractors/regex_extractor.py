# src/smalter_autodoc/core/extractors/regex_extractor.py
"""
Phase 1 : Extraction par patterns Regex (version robuste 2026)

Objectif : Extraire champs structurés depuis texte brut OCRisé
Vitesse  : ~0.05–0.15 seconde
Précision attendue : 80–92% sur factures françaises standards
                       (après nettoyage OCR + validation stricte)
"""

import re
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RegexExtractor:
    """
    Extrait des champs structurés depuis du texte brut via regex.
    
    Points forts :
    - Gestion erreurs OCR courantes (O→0, l→1, espaces parasites)
    - Normalisation dates/montants/IBAN/SIRET
    - Validation stricte (Luhn pour SIRET, format ISO pour dates)
    - Logging détaillé + tracking champs manquants
    
    Utilisation:
        extractor = RegexExtractor()
        data = extractor.extract_invoice_fields(texte_ocr)
    """


    # Pattern montant ultra-robuste (négatif, devises multiples, formats FR/EN/CH)
    AMOUNT_PATTERN = r'(?:(?:[\-−])?\s*(?:[€$£]|USD|EUR|CHF|FCFA|XOF|MAD)?\s*)?(\d{1,3}(?:[\s\.,\']?\d{3})*[.,]\d{1,2})\b'
    
    # Mots génériques à exclure pour extraction fournisseur
    GENERIC_COMPANY_WORDS = {
        'facture', 'invoice', 'devis', 'avoir', 'note', 'proforma',
        'relevé', 'extrait', 'bordereau', 'bon', 'ticket', 'reçu',
        'attestation', 'certificat', 'document', 'exemplaire'
    }



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
    


    def extract_invoice_fields(self, text: str) -> Dict[str, Any]:
        """
        Extrait les champs clés d'une facture.
        Retourne un dict avec None pour les champs non trouvés.
        """

        text = self._normalize_text(text)

        result: Dict[str, Any] = {
            "numero_facture": None,
            "date_facture": None,
            "montant_ttc": None,
            "montant_ht": None,
            "tva_rates": [],
            "fournisseur": None,
            "siret": None,
            "adresse_fournisseur": None,  # Pour Phase 2 (LLM)
            "lignes_articles": [],         # Pour Phase 2 (LLM)
            "conditions_paiement": None,   # Pour Phase 2 (LLM)
            "_missing_fields": [],
            "_extraction_method": "REGEX",
        }

        # Ordre logique : commencer par les champs les plus discriminants
        result["numero_facture"] = self._extract_invoice_number(text)
        result["date_facture"]   = self._extract_date(text)
        result["siret"]          = self._extract_siret(text)
        result["montant_ttc"]    = self._extract_ttc(text)
        result["montant_ht"]     = self._extract_ht(text)
        result["tva_rates"]      = self._extract_tva_rates(text)
        result["fournisseur"]    = self._extract_fournisseur(text)

        # Tracking des champs manquants
        missing = [k for k, v in result.items() 
                   if not k.startswith('_') and (v is None or v == [])]
        result["_missing_fields"] = missing

        logger.info(
            f"Regex facture → {len([k for k in result if not k.startswith('_')]) - len(missing)}"
            f"/{len([k for k in result if not k.startswith('_')])} champs trouvés | "
            f"Manquants: {missing}"
        )

        return result

    def extract_bank_fields(self, text: str) -> Dict[str, Any]:
        """Extrait les champs clés d'un relevé bancaire"""
        result: Dict[str, Any] = {
            "iban": None,
            "bic": None,
            "solde_initial": None,
            "solde_final": None,
            "transactions": [],  # à remplir dans une phase 2 si besoin
            "_missing_fields": [],
            "_extraction_method": "REGEX",
        }

        result["iban"]         = self._extract_iban(text)
        result["bic"]          = self._extract_bic(text)
        result["solde_final"]  = self._extract_solde(text)

        missing = [k for k, v in result.items() 
                   if not k.startswith('_') and (v is None or v == [])]
        result["_missing_fields"] = missing

        logger.info(
            f"Regex relevé bancaire → {len(result) - len(missing) - 2}/{len(result) - 2} champs | "
            f"Manquants: {missing}"
        )

        return result

    # ────────────────────────────────────────────────
    #  MÉTHODES D'EXTRACTION PRIVÉES
    # ────────────────────────────────────────────────

    def _extract_invoice_number(self, text: str) -> Optional[str]:
        """
        Extraction numéro facture (fix complet)
        
        Gère :
        - Numéros avec points : S-3.00000003
        - Numéros avec tirets : FC-2024-001
        - Numéros alphanumériques : INV2024001
        - Numéros purement numériques : 20240001
        """
        
        patterns = [
            # Pattern 1 : Avec mot-clé + numéro complexe (points/tirets acceptés)
            r'(?:facture|invoice|fac\.?|n°|no\.?|num[eé]ro)\s*[:#]?\s*([A-Z0-9]+(?:[\.\-/][A-Z0-9]+)*)',
            
            # Pattern 2 : Format structuré sans mot-clé
            r'\b([A-Z]{1,6}[-/.]\d+(?:[-.]\d+)*)\b',  # S-3.00000003
            
            # Pattern 3 : Alphanumérique classique
            r'\b([A-Z]{2,6}[-/]?\d{2,8})\b',          # FC-2024-001
            
            # Pattern 4 : Numérique pur (dernier recours)
            r'\b(\d{8,14})\b',
        ]
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                
                # Validation post-extraction
                
                # 1. Rejeter mots communs
                if val.lower() in ['date', 'total', 'ttc', 'ht', 'tva', 'client', 'page', 'n']:
                    logger.debug(f"Numéro facture rejeté (mot commun): '{val}'")
                    continue
                
                # 2. Rejeter si trop court (< 2 caractères)
                if len(val) < 2:
                    logger.debug(f"Numéro facture rejeté (trop court): '{val}'")
                    continue
                
                # 3. Accepter si >= 2 caractères et non-commun
                logger.debug(f"✅ Numéro facture: {val}")
                return val
        
        return None

    def _extract_date(self, text: str) -> Optional[str]:
        """
        Date normalisée en ISO YYYY-MM-DD
        
        Supporte :
        - Formats numériques : DD/MM/YYYY, YYYY-MM-DD
        - Formats textuels : 15 décembre 2024, December 15, 2024
        - Abréviations mois français et anglais
        """
        patterns = [
            r'\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})\b',              # DD/MM/YY ou YYYY
            r'\b(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})\b',                # YYYY-MM-DD
            r'\b(\d{1,2})\s*(janv\.?|f[ée]vr\.?|mars|avr\.?|mai|juin|juil\.?|ao[uû]t|sept\.?|oct\.?|nov\.?|d[ée]c\.?)\s*(\d{2,4})\b',
            r'\b([A-Za-zÀ-ÿ]+)\s+(\d{1,2}),?\s+(\d{2,4})\b',               # Month DD, YYYY
            r'\b(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+(\d{2,4})\b',                 # DD Month YYYY
        ]

        months = {
            # Français complets et abréviations
            "janvier":1, "jan":1, "janv":1, "janv.":1,
            "février":2, "fevrier":2, "fevr":2, "fév":2, "févr":2, "fevr.":2, "fév.":2,
            "mars":3,
            "avril":4, "avr":4, "avr.":4,
            "mai":5,
            "juin":6, "jun":6,
            "juillet":7, "juil":7, "juil.":7,
            "août":8, "aout":8, "aou":8, "aoû":8,
            "septembre":9, "sept":9, "sep":9, "sept.":9,
            "octobre":10, "oct":10, "oct.":10,
            "novembre":11, "nov":11, "nov.":11,
            "décembre":12, "decembre":12, "dec":12, "déc":12, "déc.":12, "dec.":12,
            # Anglais complets et abréviations
            "january":1, "february":2, "march":3, "april":4, "may":5, "june":6,
            "july":7, "august":8, "september":9, "october":10, "november":11, "december":12,
            "jan":1, "feb":2, "mar":3, "apr":4, "jun":6, "jul":7,
            "aug":8, "sep":9, "oct":10, "nov":11, "dec":12,
        }

        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if not m:
                continue

            groups = m.groups()
            
            try:
                # YYYY-MM-DD (groupe 0 a 4 chiffres)
                if len(groups[0]) == 4 and groups[0].isdigit():
                    year, month, day = map(int, groups)
                
                # "DD Month YYYY" (groupe 1 est texte)
                elif groups[1].replace('é','e').replace('û','u').replace('.','').isalpha():
                    month_key = groups[1].lower().replace('é','e').replace('û','u').replace('.','').strip()
                    month = months.get(month_key)
                    if not month:
                        continue
                    day, year = int(groups[0]), int(groups[2])
                
                # "Month DD, YYYY" (groupe 0 est texte)
                elif groups[0].replace('é','e').replace('û','u').replace('.','').isalpha():
                    month_key = groups[0].lower().replace('é','e').replace('û','u').replace('.','').strip()
                    month = months.get(month_key)
                    if not month:
                        continue
                    day, year = int(groups[1]), int(groups[2])
                
                # DD/MM/YY ou DD/MM/YYYY (format par défaut)
                else:
                    day, month, year = map(int, groups)

                # Gestion année sur 2 chiffres (YY → YYYY)
                if 0 <= year <= 99:
                    year += 2000 if year <= 50 else 1900

                # Validation et normalisation
                dt = datetime(year, month, day)
                iso_date = dt.strftime("%Y-%m-%d")
                logger.debug(f"Date trouvée: {iso_date}")
                return iso_date
                
            except (ValueError, TypeError, KeyError) as e:
                logger.debug(f"Échec parsing date '{m.group(0)}': {e}")
                continue

        return None

    def _extract_ttc(self, text: str) -> Optional[float]:
        """Fix: gérer tableaux multi-colonnes"""
        
        patterns = [
            # Pattern explicite avec "TTC"
            r'(?:total\s+)?ttc\s*[:=]?\s*' + self.AMOUNT_PATTERN,
            r'(?:net\s+[àa]\s+payer|à\s+régler)\s*[:=]?\s*' + self.AMOUNT_PATTERN,
            
            # Pattern tableau : "Total" suivi de 2 montants (prendre le 2ème)
            r'total\s+(?:g[ée]n[ée]ral)?\s*' + self.AMOUNT_PATTERN + r'\s+' + self.AMOUNT_PATTERN,
            
            # Somme à payer
            r'somme\s+[àa]\s+payer\s*[:=]?\s*' + self.AMOUNT_PATTERN,
        ]
        
        amounts = []
        for pat in patterns:
            matches = list(re.finditer(pat, text, re.IGNORECASE))
            for m in matches:
                # Si 2 groupes capturés (tableau), prendre le 2ème
                if m.lastindex and m.lastindex >= 2:
                    amt = self._parse_amount(m.group(m.lastindex))
                else:
                    amt = self._parse_amount(m.group(1))
                
                if amt is not None and amt != 0:
                    amounts.append(amt)
        
        if amounts:
            # Prendre le plus élevé (TTC > HT)
            value = max(amounts)
            logger.debug(f"TTC: {value}€")
            return value
        
        return None

    def _extract_ht(self, text: str) -> Optional[float]:
        """Fix: gérer tableaux multi-colonnes"""
        
        patterns = [
            # Explicite avec "HT"
            r'(?:total\s+)?(?:h\.?t\.?|hors\s+taxes?)\s*[:=]?\s*' + self.AMOUNT_PATTERN,
            
            # Tableau : "Total" + 1er montant
            r'total\s+(?:g[ée]n[ée]ral)?\s*' + self.AMOUNT_PATTERN,
        ]
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                amt = self._parse_amount(m.group(1))
                if amt:
                    logger.debug(f"HT: {amt}€")
                    return amt
        
        return None

    def _extract_tva_rates(self, text: str) -> List[float]:
        """
        Taux de TVA présents dans le document
        
        Taux valides en France 2024-2026 : 2.1%, 5.5%, 8.5%, 10%, 20%
        """
        pattern = r'(?:tva|t\.?v\.?a\.?|vat|v\.?a\.?t\.?)\s*[:=]?\s*(2[.,]1|5[.,]5|8[.,]5|10|20)\s*%?'
        
        rates = set()
        for m in re.finditer(pattern, text, re.IGNORECASE):
            rate = float(m.group(1).replace(',', '.'))
            rates.add(rate)
        
        sorted_rates = sorted(rates)
        if sorted_rates:
            logger.debug(f"Taux TVA trouvés: {sorted_rates}")
        
        return sorted_rates

    def _extract_fournisseur(self, text: str) -> Optional[str]:
        """Fix: chercher après logo/header, éviter metadata"""
        
        # Nettoyer le texte d'abord (supprimer metadata page)
        text_clean = re.sub(r'Page\s+\d+/\d+', '', text, flags=re.IGNORECASE)
        text_clean = re.sub(r'Facture\s+n°.*', '', text_clean, flags=re.IGNORECASE)
        
        patterns = [
            # Pattern avec mot-clé
            r'(?:fournisseur|vendeur|société|company)\s*[:=]?\s*([^\n\r]{3,80})',
            
            # Chercher ligne avec forme juridique
            r'\b([A-ZÀ-Ý][\w\s&]{2,50}(?:SARL|SAS|SA|Ltd|LLC|Inc|Company|Compagnie))\b',
            
            # Première ligne significative (>= 3 mots)
            r'^([A-ZÀ-Ý][^\n\r]{10,70})$',
        ]
        
        for pat in patterns:
            m = re.search(pat, text_clean, re.IGNORECASE | re.MULTILINE)
            if not m:
                continue
            
            candidate = m.group(1).strip()
            
            # Rejeter metadata
            bad_words = ['page', 'facture', 'invoice', 'date', 'total', 'client', 'reference']
            if any(bad in candidate.lower() for bad in bad_words):
                continue
            
            # Rejeter si que des chiffres
            if candidate.replace(' ', '').isdigit():
                continue
            
            # Accepter si >= 2 mots
            words = [w for w in candidate.split() if len(w) > 2]
            if len(words) >= 2:
                return candidate
        
        return None
        


    def _extract_iban(self, text: str) -> Optional[str]:
        """
        Extraction IBAN avec validation longueur selon pays
        
        Support multi-pays : FR, DE, ES, IT, BE, CH, GB, etc.
        """
        # Pattern flexible pour tous pays
        pattern = r'(?:IBAN\s*[:=]?\s*)?([A-Z]{2}\d{2}\s*(?:[A-Z0-9\s]{12,30}))\b'
        
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return None
        
        # Nettoyer et normaliser
        iban = re.sub(r'\s', '', m.group(1)).upper()
        
        # Validation longueur selon code pays
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
        else:
            logger.debug(f"IBAN invalide (longueur): {iban[:8]}... (attendu: {expected_length}, reçu: {len(iban)})")
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
        """Solde final (fix: date entre mot-clé et montant)"""
        patterns = [
            r'(?:solde\s+final|nouveau\s+solde|solde\s+cr[ée]diteur|solde\s+au)[\s\S]{0,50}?' + self.AMOUNT_PATTERN,
            r'solde\s*[:=]?\s*' + self.AMOUNT_PATTERN,
        ]
        
        amounts = []
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                amount_str = m.group(m.lastindex) if m.lastindex else m.group(1)
                amt = self._parse_amount(amount_str)
                if amt is not None:
                    amounts.append(amt)
        
        if amounts:
            value = amounts[-1]
            logger.debug(f"Solde final trouvé: {value}€")
            return value
        
        return None



    def _extract_siret(self, text: str) -> Optional[str]:
        """Fix: prendre PREMIER SIRET (= fournisseur)"""
        
        patterns = [
            r'\bSIRET\b\s*(?:n°|num[eé]ro)?\s*[:\-]?\s*([\d\s]{14,20})',
            r'(?:siret|siren)\s*[:=]?\s*(\d[\d\s]{12,18}\d)',
            r'\b(\d{3}\s+\d{3}\s+\d{3}\s+\d{5})\b',
        ]
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)  # Premier match seulement
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
        cleaned = re.sub(r'[€$£]|CHF|EUR|USD|FCFA|XOF|GBP', '', cleaned)
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