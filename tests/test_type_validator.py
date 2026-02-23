# tests/test_type_validator.py

from src.smalter_autodoc.core.document_type_validator import DocumentTypeValidator

def test_facture_valide():
    validator = DocumentTypeValidator()
    
    text = """
    FACTURE N° F2024-001
    Date : 15/12/2024
    Total TTC : 120.00 €
    """
    
    result = validator.validate(text, "FACTURE")
    
    assert result["valid"] == True
    assert result["confidence"] >= 50

def test_devis_declare_comme_facture():
    validator = DocumentTypeValidator()
    
    text = """
    DEVIS N° DEV2024-001
    Date : 15/12/2024
    Total TTC : 120.00 €
    """
    
    result = validator.validate(text, "FACTURE")
    
    assert result["valid"] == False
    assert result["detected_type"] == "DEVIS"
    assert "DEVIS" in result["reason"]

def test_facture_sans_mot_cle():
    validator = DocumentTypeValidator()
    
    text = """
    Document N° 2024-001
    Date : 15/12/2024
    Total : 120.00 €
    """
    
    result = validator.validate(text, "FACTURE")
    
    # Avertissement mais pas rejet
    assert result["valid"] == True
    assert result["confidence"] == 50.0
