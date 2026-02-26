# src/smalter_autodoc/core/document_router.py

from typing import Optional, Dict, Type
from src.smalter_autodoc.core.agents.invoice_agent import InvoiceAgent
from src.smalter_autodoc.core.agents.bank_agent import BankAgent
from src.smalter_autodoc.core.agents.cash_agent import CashAgent
from src.smalter_autodoc.core.agents.base_agent import BaseDocumentAgent
from src.smalter_autodoc.core.extractors.hybrid_extractor import HybridExtractor
import logging

logger = logging.getLogger(__name__)

class DocumentRouter:
    """
    Router qui sélectionne l'agent selon type déclaré
    
    Support multi-langues via HybridExtractor
    """
    
    # Registre des agents (attribut de classe)
    AGENT_REGISTRY: Dict[str, Type[BaseDocumentAgent]] = {
        "FACTURE": InvoiceAgent,
        "RELEVE_BANCAIRE": BankAgent,
        "TICKET_Z": CashAgent,
    }
    
    def __init__(self, use_llm: bool = True, language: str = 'fr'):
        """
        Args:
            use_llm: Activer LLM dans HybridExtractor
            language: Langue pour patterns Regex (fr, en, ar...)
        """
        self.use_llm = use_llm
        self.language = language
        self._agents_cache: Dict[str, BaseDocumentAgent] = {}
        
        logger.info(
            f"DocumentRouter initialisé "
            f"(Langue: {language}, LLM: {'activé' if use_llm else 'désactivé'})"
        )
    
    def get_agent(self, document_type: str) -> Optional[BaseDocumentAgent]:
        """
        Retourne agent pour le type demandé (avec langue configurée)
        
        Args:
            document_type: "FACTURE", "RELEVE_BANCAIRE", "TICKET_Z"
            
        Returns:
            Instance de l'agent ou None si type inconnu
        """
        
        document_type = document_type.upper().strip()
        
        # Vérifier type supporté
        if document_type not in self.AGENT_REGISTRY:  # ← FIX : self.AGENT_REGISTRY
            logger.error(
                f"Type de document inconnu : '{document_type}'. "
                f"Types supportés : {list(self.AGENT_REGISTRY.keys())}"
            )
            return None
        
        # Cache par (type, langue) pour éviter recréation
        cache_key = f"{document_type}_{self.language}"
        
        if cache_key not in self._agents_cache:
            agent_class = self.AGENT_REGISTRY[document_type]
            
            # Créer HybridExtractor avec config langue
            extractor = HybridExtractor(
                use_llm=self.use_llm,
                language=self.language
            )
            
            # Instancier agent avec extractor configuré
            agent = agent_class(extractor=extractor)
            
            # Cache
            self._agents_cache[cache_key] = agent
            
            logger.info(
                f"Instanciation {agent.agent_name} pour type '{document_type}' "
                f"(langue: {self.language})"
            )
        
        return self._agents_cache[cache_key]
    
    def list_supported_types(self) -> list:
        """Liste types de documents supportés"""
        return list(self.AGENT_REGISTRY.keys())