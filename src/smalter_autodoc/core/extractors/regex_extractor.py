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
    AMOUNT_PATTERN = r'(?:(?:[\-−])?\s*(?:[€$£]|USD|EUR|CHF|FCFA|XOF)?\s*)?(\d{1,3}(?:[\s\.,\']?\d{3})*[.,]\d{1,2})\b'
    
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
        Numéro de facture — très fréquent en 2025–2026
        
        Priorité : patterns avec mots-clés > patterns génériques
        """
        patterns = [
            # Patterns spécifiques (avec mot-clé)
            r'\b(?:facture|invoice|fac\.?|n°|no\.?|num[eé]ro|ref|reference|doc|fc)\b\s*[:#.\-/]?\s*([A-Z0-9][A-Z0-9\-/]{2,35})\b',
            # Patterns structurés typiques
            r'\b([A-Z]{2,6}[-/]?\d{2,6}[-/]?\d{2,8})\b',          # FC24-00123, INV-2025-456
            r'\b\d{4}[/-]\d{2,8}\b',                               # 2024/00123456
            # Pattern générique (dernier recours)
            r'\b(\d{8,14})\b',                                     # 00000123456789 (8-14 chiffres)
        ]
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                logger.debug(f"Numéro facture trouvé: {val}")
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
        """
        Montant TTC — priorité aux mots-clés forts
        
        Stratégie : Chercher patterns spécifiques puis prendre le montant le plus élevé
        (le TTC est généralement le total final)
        """
        patterns = [
            # Patterns très spécifiques (priorité haute)
            r'(?:net\s+[àa]\s+payer|à\s+r[ée]gle?r|solde\s+[àa]\s+payer)\s*[:=]?\s*' + self.AMOUNT_PATTERN,
            r'(?:total\s+)?ttc\s*[:=]?\s*' + self.AMOUNT_PATTERN,
            # Patterns moyennement spécifiques
            r'total\s+(?:g[eé]n[eé]ral|facture|à\s+payer)?\s*[:=]?\s*' + self.AMOUNT_PATTERN,
            # Pattern générique (dernier recours)
            r'\btotal\s*[:=]?\s*' + self.AMOUNT_PATTERN,
        ]

        amounts = []
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                amt = self._parse_amount(m.group(1))
                if amt is not None and amt != 0:
                    amounts.append(amt)

        if amounts:
            # Prendre le plus élevé (TTC = total final)
            value = max(amounts)
            logger.debug(f"Montant TTC trouvé: {value}€ (parmi {len(amounts)} candidats)")
            return value
        
        return None

    def _extract_ht(self, text: str) -> Optional[float]:
        """Montant HT (Hors Taxes)"""
        patterns = [
            r'(?:total\s+)?(?:h\.?t\.?|hors\s+taxes?)\s*[:=]?\s*' + self.AMOUNT_PATTERN,
            r'montant\s+hors\s+taxes?\s*[:=]?\s*' + self.AMOUNT_PATTERN,
            r'\bht\b\s*[:=]?\s*' + self.AMOUNT_PATTERN,
        ]
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                amt = self._parse_amount(m.group(1))
                if amt is not None:
                    logger.debug(f"Montant HT trouvé: {amt}€")
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
        """
        Extraction nom fournisseur avec filtrage anti-faux-positifs
        
        Stratégie :
        1. Chercher patterns avec mots-clés
        2. Sinon, première ligne significative (avec validation stricte)
        3. Rejeter mots génériques et formats suspects
        """
        patterns = [
            # Patterns avec mots-clés explicites
            r'(?:fournisseur|[eé]metteur|vendeur|soci[ée]t[ée]|raison\s+sociale)\s*[:=]?\s*([^\n\r]{3,80})',
            # Première ligne (avec validation stricte après)
            r'^([A-ZÀ-Ý][^\n\r]{5,70})(?:\n|$)',
        ]
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
            if not m:
                continue
            
            candidate = m.group(1).strip()
            
            # Validation stricte
            words = candidate.lower().split()
            
            # 1. Rejeter si contient mot générique
            if any(generic in candidate.lower() for generic in self.GENERIC_COMPANY_WORDS):
                logger.debug(f"Candidat fournisseur rejeté (mot générique): '{candidate}'")
                continue
            
            # 2. Rejeter si trop court ou que des chiffres
            if len(candidate) < 3 or candidate.replace(' ', '').isdigit():
                continue
            
            # 3. Accepter si forme juridique présente (forte indication)
            legal_forms = ['SARL', 'SAS', 'SA ', 'EURL', 'SCI', 'SASU', 'SNC', 'SCOP', 'GIE']
            has_legal_form = any(form in candidate.upper() for form in legal_forms)
            
            # 4. Accepter si >= 2 mots ET pas que des majuscules (évite "FACTURE DE VENTE")
            is_multi_word = len(words) >= 2
            not_all_caps = candidate != candidate.upper()
            
            if has_legal_form or (is_multi_word and not_all_caps):
                logger.debug(f"Fournisseur trouvé: '{candidate}'")
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
        """Solde final d'un relevé bancaire"""
        patterns = [
            r'(?:solde\s+(?:final|au|au\s+\d{1,2}[/-]\d{1,2})?|nouveau\s+solde|solde\s+cr[ée]diteur)\s*[:=]?\s*' + self.AMOUNT_PATTERN,
        ]
        
        amounts = []
        for pat in patterns:
            for m in re.finditer(pat, text, re.IGNORECASE):
                amt = self._parse_amount(m.group(1))
                if amt is not None:
                    amounts.append(amt)
        
        if amounts:
            value = max(amounts)
            logger.debug(f"Solde final trouvé: {value}€")
            return value
        
        return None

    def _extract_siret(self, text: str) -> Optional[str]:
        """
        Extraction SIRET avec validation Luhn
        
        SIRET = 14 chiffres (SIREN 9 chiffres + NIC 5 chiffres)
        Validation : Algorithme de Luhn adapté
        """
        # Patterns par ordre de spécificité (du plus au moins spécifique)
        patterns = [
            # Avec mot-clé explicite (haute confiance)
            r'\bSIRET\b\s*(?:n°|num[eé]ro)?\s*[:\-]?\s*([\d\s]{14,20})',
            r'(?:siret|siren)\s*[:=]?\s*(\d[\d\s]{12,18}\d)',
            # Format espacé typique 123 456 789 00012
            r'\b(\d{3}\s+\d{3}\s+\d{3}\s+\d{5})\b',
            # Format sans espaces (utilisé en dernier recours avec validation contexte)
            # r'\b(\d{14})\b',  # Commenté car trop générique sans contexte
        ]
        
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if not m:
                continue
            
            # Nettoyer
            cleaned = re.sub(r'\s', '', m.group(1))
            
            # Vérifier longueur exacte
            if len(cleaned) != 14 or not cleaned.isdigit():
                continue
            
            # Validation Luhn pour SIRET
            if self._validate_siret_luhn(cleaned):
                logger.debug(f"SIRET valide trouvé: {cleaned}")
                return cleaned
            else:
                logger.debug(f"SIRET invalide (Luhn): {cleaned}")
        
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