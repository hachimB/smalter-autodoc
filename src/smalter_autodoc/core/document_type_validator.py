# src/smalter_autodoc/core/document_type_validator.py
"""
Valide que le type déclaré correspond au contenu du document
"""

import re
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class DocumentTypeValidator:
    """
    Vérifie cohérence entre type déclaré et contenu réel
    
    Méthode : Recherche mots-clés spécifiques dans le texte
    """
    
    # Mots-clés par type de document
    TYPE_KEYWORDS = {
        "FACTURE": {
            "required": ["facture", "invoice"],
            "forbidden": ["devis", "quote", "proforma", "bon de commande", "purchase order"]
        },
        "DEVIS": {
            "required": ["devis", "quote", "proforma"],
            "forbidden": ["facture", "invoice"]
        },
        "RELEVE_BANCAIRE": {
            "required": ["relevé", "extrait", "compte", "bank statement"],
            "forbidden": ["facture", "devis"]
        },
        "TICKET_Z": {
            "required": ["ticket z", "rapport de caisse", "z-report"],
            "forbidden": ["facture", "devis"]
        },
    }
    
    def validate(
        self, 
        text: str, 
        declared_type: str
    ) -> Dict[str, any]:
        """
        Vérifie cohérence type déclaré vs contenu
        
        Args:
            text: Texte extrait du document
            declared_type: Type déclaré par utilisateur
            
        Returns:
            {
                "valid": bool,
                "declared_type": str,
                "detected_type": str or None,
                "confidence": float (0-100),
                "reason": str
            }
        """
        
        declared_type = declared_type.upper().strip()
        
        # Vérifier que le type est supporté
        if declared_type not in self.TYPE_KEYWORDS:
            return {
                "valid": False,
                "declared_type": declared_type,
                "detected_type": None,
                "confidence": 0.0,
                "reason": f"Type '{declared_type}' non supporté"
            }
        
        text_lower = text.lower()
        
        keywords = self.TYPE_KEYWORDS[declared_type]
        
        # ══════════════════════════════════════════════
        # 1. Vérifier présence mots-clés requis
        # ══════════════════════════════════════════════
        
        required_found = []
        for keyword in keywords["required"]:
            if keyword.lower() in text_lower:
                required_found.append(keyword)
        
        # ══════════════════════════════════════════════
        # 2. Vérifier absence mots-clés interdits
        # ══════════════════════════════════════════════
        
        forbidden_found = []
        for keyword in keywords["forbidden"]:
            if keyword.lower() in text_lower:
                forbidden_found.append(keyword)
        
        # ══════════════════════════════════════════════
        # 3. Détecter type réel si incohérence
        # ══════════════════════════════════════════════
        
        detected_type = None
        if forbidden_found:
            # Chercher quel type correspond aux mots interdits
            for doc_type, kw in self.TYPE_KEYWORDS.items():
                if any(fb in kw["required"] for fb in forbidden_found):
                    detected_type = doc_type
                    break
        
        # ══════════════════════════════════════════════
        # 4. Décision finale
        # ══════════════════════════════════════════════
        
        # Cas 1 : Mots interdits trouvés → REJET
        if forbidden_found:
            confidence = 0.0
            valid = False
            reason = (
                f"Document semble être un '{detected_type}' "
                f"(mots trouvés : {', '.join(forbidden_found)}), "
                f"pas un '{declared_type}'"
            )
        
        # Cas 2 : Aucun mot requis trouvé → AVERTISSEMENT (pas rejet)
        elif not required_found:
            confidence = 50.0  # Incertitude
            valid = True  # On laisse passer quand même
            reason = (
                f"Aucun mot-clé '{declared_type}' trouvé dans le texte. "
                f"Vérifiez que le type déclaré est correct."
            )
        
        # Cas 3 : Mots requis trouvés, pas d'interdit → OK
        else:
            confidence = min(100.0, len(required_found) * 50.0)
            valid = True
            reason = f"Type '{declared_type}' confirmé (mots trouvés : {', '.join(required_found)})"
        
        logger.info(
            f"Validation type : {declared_type} → "
            f"{'✅ VALIDE' if valid else '❌ INVALIDE'} "
            f"(confiance: {confidence}%)"
        )
        
        return {
            "valid": valid,
            "declared_type": declared_type,
            "detected_type": detected_type,
            "confidence": confidence,
            "reason": reason
        }