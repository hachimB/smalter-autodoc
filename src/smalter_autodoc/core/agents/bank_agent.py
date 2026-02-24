"""
Agent Relevés Bancaires : Traite les relevés de compte

Gère :
- Relevés de compte courant
- Extraits bancaires mensuels

Champs obligatoires :
- IBAN (identification compte)
- Solde final (état du compte)
"""

from src.smalter_autodoc.core.agents.base_agent import BaseDocumentAgent
import logging

logger = logging.getLogger(__name__)

class BankAgent(BaseDocumentAgent):
    """
    Agent spécialisé pour les relevés bancaires
    
    Validation stricte :
    - IBAN obligatoire (identification compte)
    - Solde final obligatoire (état du compte)
    
    Champs optionnels :
    - BIC (identification banque)
    - Solde initial (vérification cohérence)
    - Transactions (détail opérations)
    """
    
    document_type = "RELEVE_BANCAIRE"
    agent_name = "BankAgent"
    
    required_fields = [
        "iban",
        "solde_final",
    ]
    
    optional_fields = [
        "bic",
        "solde_initial",
        "transactions",
    ]

    field_hints = {
        "iban": "numéro IBAN du compte bancaire",
        "bic": "code BIC/SWIFT de la banque",
        "solde_initial": "solde du compte en début de période",
        "solde_final": "solde du compte en fin de période",
        "transactions": "liste des opérations bancaires avec date, libellé et montant",
    }
    
    def __init__(self, extractor):
        super().__init__(extractor)
        logger.info(
            f"{self.agent_name} configuré : "
            f"{len(self.required_fields)} champs requis"
        )