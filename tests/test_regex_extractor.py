# tests/unit/test_regex_extractor_complete.py
"""
Tests unitaires complets pour RegexExtractor
Couvre tous les cas limites et erreurs OCR
"""

import pytest
from src.smalter_autodoc.core.extractors.regex_extractor import RegexExtractor

class TestRegexExtractor:
    
    @pytest.fixture
    def extractor(self):
        return RegexExtractor()
    
    # ══════════════════════════════════════════════════════
    # TESTS MONTANTS
    # ══════════════════════════════════════════════════════
    
    def test_parse_amount_french_format(self, extractor):
        """Format français : 1.234,56"""
        assert extractor._parse_amount("1.234,56") == 1234.56
        assert extractor._parse_amount("108,40") == 108.40
    
    def test_parse_amount_english_format(self, extractor):
        """Format anglais : 1,234.56"""
        assert extractor._parse_amount("1,234.56") == 1234.56
        assert extractor._parse_amount("108.40") == 108.40
    
    def test_parse_amount_swiss_format(self, extractor):
        """Format suisse : 1'234.56"""
        assert extractor._parse_amount("1'234.56") == 1234.56
    
    def test_parse_amount_ocr_errors(self, extractor):
        """Corrections OCR : O→0, l→1"""
        assert extractor._parse_amount("1O8,4O") == 108.40
        assert extractor._parse_amount("l23,45") == 123.45
    
    def test_parse_amount_negative(self, extractor):
        """Montants négatifs (avoirs)"""
        assert extractor._parse_amount("-120,50") == -120.50
    
    def test_parse_amount_with_currency(self, extractor):
        """Avec symboles monétaires"""
        assert extractor._parse_amount("€ 120,50") == 120.50
        assert extractor._parse_amount("120,50 EUR") == 120.50
    
    # ══════════════════════════════════════════════════════
    # TESTS DATES
    # ══════════════════════════════════════════════════════
    
    def test_extract_date_french_numeric(self, extractor):
        """Format français : 15/12/2024"""
        text = "Date : 15/12/2024"
        assert extractor._extract_date(text) == "2024-12-15"
    
    def test_extract_date_iso(self, extractor):
        """Format ISO : 2024-12-15"""
        text = "Date : 2024-12-15"
        assert extractor._extract_date(text) == "2024-12-15"
    
    def test_extract_date_french_text(self, extractor):
        """Format textuel français : 15 décembre 2024"""
        text = "Le 15 décembre 2024"
        assert extractor._extract_date(text) == "2024-12-15"
    
    def test_extract_date_english_text(self, extractor):
        """Format textuel anglais : December 15, 2024"""
        text = "Date: December 15, 2024"
        assert extractor._extract_date(text) == "2024-12-15"
    
    def test_extract_date_two_digit_year(self, extractor):
        """Année sur 2 chiffres : 15/12/24"""
        text = "15/12/24"
        assert extractor._extract_date(text) == "2024-12-15"
    
    # ══════════════════════════════════════════════════════
    # TESTS SIRET
    # ══════════════════════════════════════════════════════
    
    def test_validate_siret_luhn_valid(self, extractor):
        """SIRET valide avec Luhn"""
        assert extractor._validate_siret_luhn("73282932000074") == True
    
    def test_validate_siret_luhn_invalid(self, extractor):
        """SIRET invalide (dernier chiffre modifié)"""
        assert extractor._validate_siret_luhn("73282932000075") == False
    
    def test_extract_siret_with_spaces(self, extractor):
        """SIRET avec espaces : 732 829 320 00074"""
        text = "SIRET : 732 829 320 00074"
        assert extractor._extract_siret(text) == "73282932000074"
    
    def test_extract_siret_without_keyword(self, extractor):
        """SIRET sans mot-clé (format espacé)"""
        text = "Entreprise 732 829 320 00074 située à Paris"
        assert extractor._extract_siret(text) == "73282932000074"
    
    # ══════════════════════════════════════════════════════
    # TESTS IBAN
    # ══════════════════════════════════════════════════════
    
    def test_extract_iban_france(self, extractor):
        """IBAN français (27 caractères)"""
        # IBAN réel format (fictif mais valide en structure)
        text = "IBAN : FR14 2004 1010 0505 0001 3M02 606"
        result = extractor._extract_iban(text)
        assert result is not None
        assert len(result) == 27
        assert result.startswith("FR")
    
    def test_extract_iban_germany(self, extractor):
        """IBAN allemand (22 caractères)"""
        text = "IBAN: DE89 3704 0044 0532 0130 00"
        result = extractor._extract_iban(text)
        assert result and len(result) == 22
    
    # ══════════════════════════════════════════════════════
    # TESTS FOURNISSEUR
    # ══════════════════════════════════════════════════════
    
    def test_extract_fournisseur_with_legal_form(self, extractor):
        """Fournisseur avec forme juridique"""
        text = "Tech Solutions SARL\n123 Rue Paris"
        assert extractor._extract_fournisseur(text) == "Tech Solutions SARL"
    
    def test_extract_fournisseur_reject_generic(self, extractor):
        """Rejeter titres génériques"""
        text = "FACTURE DE VENTE\nCarrefour Market"
        result = extractor._extract_fournisseur(text)
        # Ne doit PAS retourner "FACTURE DE VENTE"
        assert result != "FACTURE DE VENTE"
    
    # ══════════════════════════════════════════════════════
    # TESTS EXTRACTION COMPLÈTE FACTURE
    # ══════════════════════════════════════════════════════
    
    def test_extract_invoice_complete(self, extractor):
        """Test extraction facture complète"""
        # SANS indentation (texte réaliste OCR)
        text = """
Carrefour Market SARL
123 Rue de Paris, 75001 Paris
SIRET : 732 829 320 00074

FACTURE N° F2024-001
Date : 15/12/2024

Total HT    100,00 €
TVA 20%      20,00 €
Total TTC   120,00 €
"""
        
        result = extractor.extract_invoice_fields(text)
        
        # Assertions
        assert result['numero_facture'] == "F2024-001", \
            f"Num facture attendu: F2024-001, reçu: {result['numero_facture']}"
        
        assert result['date_facture'] == "2024-12-15", \
            f"Date attendue: 2024-12-15, reçue: {result['date_facture']}"
        
        assert result['montant_ttc'] == 120.00, \
            f"TTC attendu: 120.00, reçu: {result['montant_ttc']}"
        
        assert result['montant_ht'] == 100.00, \
            f"HT attendu: 100.00, reçu: {result['montant_ht']}"
        
        assert result['tva_rates'] == [20.0], \
            f"TVA attendue: [20.0], reçue: {result['tva_rates']}"
        
        assert result['siret'] == "73282932000074", \
            f"SIRET attendu: 73282932000074, reçu: {result['siret']}"
        
        assert result['fournisseur'] is not None, \
            "Fournisseur devrait être extrait"
        assert "Carrefour" in result['fournisseur'], \
            f"Fournisseur devrait contenir 'Carrefour', reçu: {result['fournisseur']}"
        
        # Vérifier champs manquants
        missing = result['_missing_fields']
        assert 'numero_facture' not in missing
        assert 'date_facture' not in missing
        assert 'montant_ttc' not in missing