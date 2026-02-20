"""
Document Router : Sélectionne l'agent approprié selon le type

Architecture simplifiée :
- L'utilisateur déclare le type en frontend
- Le router instancie l'agent correspondant
- L'agent traite le document
"""

from typing import Optional
from src.smalter_autodoc.core.agents.invoice_agent import InvoiceAgent
from src.smalter_autodoc.core.agents.bank_agent import BankAgent
from src.smalter_autodoc.core.agents.cash_agent import CashAgent
from src.smalter_autodoc.core.agents.base_agent import BaseDocumentAgent
from src.smalter_autodoc.core.extractors.hybrid_extractor import HybridExtractor
import logging

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# REGISTRE DES AGENTS DISPONIBLES
# ══════════════════════════════════════════════════════════════

AGENT_REGISTRY = {
    "FACTURE": InvoiceAgent,
    "RELEVE_BANCAIRE": BankAgent,
    "TICKET_Z": CashAgent,
}

class DocumentRouter:
    """
    Router simple : Sélectionne l'agent selon le type déclaré
    
    Principe :
    - Pas d'analyse ML pour déterminer le type
    - L'utilisateur a déjà sélectionné le type en frontend
    - On instancie juste le bon agent
    
    Utilisation :
        >>> router = DocumentRouter()
        >>> agent = router.get_agent("FACTURE")
        >>> result = agent.process(texte_ocr)
    """
    
    def __init__(self, use_llm: bool = True):
        """
        Args:
            use_llm: Activer/désactiver le LLM dans HybridExtractor
        """
        # Créer un extracteur partagé par tous les agents
        self.extractor = HybridExtractor(use_llm=use_llm)
        
        # Cache des agents instanciés (pour éviter re-création)
        self._agents_cache = {}
        
        logger.info(
            f"DocumentRouter initialisé avec {len(AGENT_REGISTRY)} agents disponibles"
        )
    
    def get_agent(self, document_type: str) -> Optional[BaseDocumentAgent]:
        """
        Retourne l'agent correspondant au type déclaré
        
        Args:
            document_type: Type déclaré par l'utilisateur
                          ("FACTURE", "RELEVE_BANCAIRE", "TICKET_Z")
        
        Returns:
            Instance de l'agent approprié, ou None si type inconnu
        """
        
        document_type = document_type.upper().strip()
        
        # Vérifier si agent existe
        agent_class = AGENT_REGISTRY.get(document_type)
        
        if not agent_class:
            logger.warning(
                f"Type de document inconnu : '{document_type}'. "
                f"Types supportés : {list(AGENT_REGISTRY.keys())}"
            )
            return None
        
        # Utiliser le cache si déjà instancié
        if document_type not in self._agents_cache:
            logger.info(f"Instanciation {agent_class.__name__} pour type '{document_type}'")
            self._agents_cache[document_type] = agent_class(self.extractor)
        
        return self._agents_cache[document_type]
    
    def list_supported_types(self) -> list:
        """
        Liste des types de documents supportés
        
        Returns:
            Liste des types disponibles
        """
        return list(AGENT_REGISTRY.keys())