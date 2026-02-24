"""
Agent Factures : Spécialisé dans le traitement des factures

Gère :
- Factures d'achat (fournisseurs)
- Factures de vente (clients)
- Avoirs

Champs obligatoires :
- numero_facture
- date_facture
- montant_ttc
- fournisseur (ou client selon sens)
"""

from src.smalter_autodoc.core.agents.base_agent import BaseDocumentAgent
import logging

logger = logging.getLogger(__name__)

class InvoiceAgent(BaseDocumentAgent):
    """
    Agent spécialisé pour les factures
    
    Validation stricte :
    - Numéro facture obligatoire
    - Date obligatoire
    - Montant TTC obligatoire
    - Fournisseur obligatoire
    
    Champs optionnels mais recommandés :
    - SIRET (identification entreprise)
    - Montant HT (calcul TVA)
    - Taux TVA (vérification cohérence)
    - Adresse fournisseur (archivage)
    """
    
    document_type = "FACTURE"
    agent_name = "InvoiceAgent"
    
    # Champs obligatoires (rejet si manquants)
    required_fields = [
        "numero_facture",
        "date_facture",
        "montant_ttc",
       "fournisseur",
    ]
    
    # Champs optionnels (warnings si manquants)
    optional_fields = [
        "siret",
        "montant_ht",
        "tva_rates",
        "adresse_fournisseur",
        "conditions_paiement",
    ]

    field_hints = {
        "fournisseur": "nom complet de l'entreprise émettrice de la facture",
        "adresse_fournisseur": "adresse complète du fournisseur (rue, code postal, ville)",
        "client": "nom de l'entreprise destinataire de la facture",
        "adresse_client": "adresse complète du client",
        "lignes_articles": "liste détaillée des produits ou services facturés avec description, quantité et prix",
        "conditions_paiement": "conditions ou délai de paiement indiqué sur la facture (ex: '30 jours fin de mois')",
    }
    
    def __init__(self, extractor):
        super().__init__(extractor)
        logger.info(
            f"{self.agent_name} configuré : "
            f"{len(self.required_fields)} champs requis, "
            f"{len(self.optional_fields)} optionnels"
        )