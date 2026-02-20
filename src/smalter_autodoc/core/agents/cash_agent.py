"""
Agent Tickets Z : Traite les rapports de caisse

Gère :
- Tickets Z quotidiens
- Rapports de caisse

Champs obligatoires :
- Date du rapport
- Montant total encaissé

Note : Pour l'instant, extraction basique.
Peut être enrichi plus tard avec :
- Détail modes de paiement (CB, espèces, chèques)
- Nombre de transactions
- Ticket moyen
"""

from src.smalter_autodoc.core.agents.base_agent import BaseDocumentAgent
import logging

logger = logging.getLogger(__name__)

class CashAgent(BaseDocumentAgent):
    """
    Agent spécialisé pour les tickets Z / rapports de caisse
    
    Validation stricte :
    - Date du rapport
    - Montant total (chiffre d'affaires)
    
    Champs optionnels :
    - Détail modes de paiement
    - Nombre de transactions
    """
    
    document_type = "TICKET_Z"
    agent_name = "CashAgent"
    
    required_fields = [
        "date_facture",  # Date du rapport
        "montant_ttc",   # CA total
    ]
    
    optional_fields = [
        "fournisseur",  # Nom du commerce
    ]

    field_hints = {
        "date_facture": "date du rapport de caisse",
        "montant_ttc": "montant total encaissé dans la journée",
        "fournisseur": "nom du point de vente ou commerce",
    }
    
    def __init__(self, extractor):
        super().__init__(extractor)
        logger.info(
            f"{self.agent_name} configuré : "
            f"{len(self.required_fields)} champs requis"
        )