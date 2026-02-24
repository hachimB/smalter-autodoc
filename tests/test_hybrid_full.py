# test_hybrid_full.py
"""
Test complet de l'architecture hybride Regex + LLM
"""

from src.smalter_autodoc.core.extractors.hybrid_extractor import HybridExtractor
import json

# Initialiser
extractor = HybridExtractor(use_llm=True)

# Test avec texte OCR réaliste
texte_facture = """
Carrefour Market SARL
123 Rue de Paris
75001 Paris
SIRET : 732 829 320 00074

FACTURE N° F2024-001
Date : 15/12/2024

Désignation                  Qté    PU HT     Total HT
Alimentation                 1      80,00     80,00
Produits d'hygiène           1      20,00     20,00

Total HT                                      100,00 €
TVA 20%                                        20,00 €
Total TTC                                     120,00 €

Conditions de paiement : 30 jours fin de mois
"""

print("═══════════════════════════════════════")
print("TEST EXTRACTION HYBRIDE")
print("═══════════════════════════════════════\n")

result = extractor.extract(texte_facture, "FACTURE")

print("\n═══════════════════════════════════════")
print("RÉSULTATS EXTRACTION")
print("═══════════════════════════════════════\n")

print(f"Méthode : {result['_extraction_method']}")
print(f"\n{'='*50}\n")

# Séparer les résultats par source
regex_fields = ["numero_facture", "date_facture", "siret", "montant_ttc", "montant_ht", "tva_rates"]
llm_fields = ["fournisseur", "adresse_fournisseur", "conditions_paiement", "lignes_articles"]

print("📐 CHAMPS EXTRAITS PAR REGEX :")
for field in regex_fields:
    if field in result and result[field] is not None:
        print(f"  ✓ {field:20s} : {result[field]}")

print(f"\n{'='*50}\n")

print("🤖 CHAMPS EXTRAITS PAR LLM :")
for field in llm_fields:
    if field in result and result[field] not in [None, [], {}]:
        value = result[field]
        if isinstance(value, str) and len(value) > 60:
            value = value[:57] + "..."
        print(f"  ✓ {field:20s} : {value}")

print(f"\n{'='*50}\n")

print("❌ CHAMPS MANQUANTS :")
if result["_missing_fields"]:
    for field in result["_missing_fields"]:
        print(f"  - {field}")
else:
    print("  Aucun ! Tous les champs ont été extraits.")

print(f"\n{'='*50}\n")

# Export JSON complet (optionnel)
print("JSON COMPLET (pour debug) :")
print(json.dumps(result, indent=2, ensure_ascii=False))