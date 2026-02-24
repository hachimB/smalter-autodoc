# test_agents.py
"""
Test complet du système d'agents
"""

from src.smalter_autodoc.core.document_router import DocumentRouter

# Initialiser le router
router = DocumentRouter(use_llm=True)

print("═══════════════════════════════════════════════════════")
print("TEST SYSTÈME D'AGENTS")
print("═══════════════════════════════════════════════════════\n")

# Lister types supportés
print(f"Types supportés : {router.list_supported_types()}\n")

# ══════════════════════════════════════════════════════════════
# TEST 1 : FACTURE COMPLÈTE
# ══════════════════════════════════════════════════════════════

print("─" * 60)
print("TEST 1 : FACTURE COMPLÈTE")
print("─" * 60)

texte_facture = """
Carrefour Market SARL
123 Rue de Paris, 75001 Paris
SIRET : 732 829 320 00074

FACTURE N° F2024-001
Date : 15/12/2024

Total HT    100,00 €
TVA 20%      20,00 €
Total TTC   120,00 €

Conditions : 30 jours fin de mois
"""

agent = router.get_agent("FACTURE")
result = agent.process(texte_facture)

print(f"\nAgent        : {result.agent_name}")
print(f"Succès       : {result.success}")
print(f"Confiance    : {result.confidence_score}%")
print(f"Méthode      : {result.extraction_method}")
print(f"{result.extracted_data}")

if result.success:
    print(f"\n✅ Champs extraits :")
    for field in agent.required_fields:
        value = result.extracted_data.get(field)
        print(f"   {field:20s} : {value}")
else:
    print(f"\n❌ Champs manquants : {result.missing_required_fields}")

if result.warnings:
    print(f"\n⚠️  Warnings :")
    for warning in result.warnings:
        print(f"   - {warning}")

# ══════════════════════════════════════════════════════════════
# TEST 2 : FACTURE INCOMPLÈTE (manque numéro)
# ══════════════════════════════════════════════════════════════

print("\n" + "─" * 60)
print("TEST 2 : FACTURE INCOMPLÈTE")
print("─" * 60)

texte_incomplet = """
Carrefour Market
Date : 15/12/2024
Total TTC   120,00 €
"""

agent = router.get_agent("FACTURE")
result = agent.process(texte_incomplet)

print(f"\nSuccès       : {result.success}")
print(f"Confiance    : {result.confidence_score}%")
print(f"{result.extracted_data}")

if not result.success:
    print(f"\n❌ Erreurs :")
    for error in result.errors:
        print(f"   - {error}")

# ══════════════════════════════════════════════════════════════
# TEST 3 : RELEVÉ BANCAIRE
# ══════════════════════════════════════════════════════════════

print("\n" + "─" * 60)
print("TEST 3 : RELEVÉ BANCAIRE")
print("─" * 60)

texte_releve = """
BNP PARIBAS
IBAN : FR14 2004 1010 0505 0001 3M02 606
BIC : BNPAFRPP

Relevé du 01/12/2024 au 31/12/2024

Solde au 01/12/2024 :  1 500,00 €
Solde au 31/12/2024 :  2 300,00 €
"""

agent = router.get_agent("RELEVE_BANCAIRE")
result = agent.process(texte_releve)

print(f"\nAgent        : {result.agent_name}")
print(f"Succès       : {result.success}")
print(f"Confiance    : {result.confidence_score}%")
print(f"{result.extracted_data}")

if result.success:
    print(f"\n✅ Champs extraits :")
    for field in agent.required_fields:
        value = result.extracted_data.get(field)
        print(f"   {field:20s} : {value}")

# ══════════════════════════════════════════════════════════════
# TEST 4 : TYPE INCONNU
# ══════════════════════════════════════════════════════════════

print("\n" + "─" * 60)
print("TEST 4 : TYPE INCONNU")
print("─" * 60)

agent = router.get_agent("CONTRAT")
print(f"Agent retourné : {agent}")

print("\n" + "═" * 60)