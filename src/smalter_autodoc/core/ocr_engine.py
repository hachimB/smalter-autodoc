# src/smalter_autodoc/core/ocr_engine.py
"""
PORTE 2 : Extraction Texte (OCR ou Direct)

Deux stratégies selon type de document:
1. PDF Natif → Extraction directe (PyPDF2)
2. Image/PDF Scan → OCR Tesseract avec scores
"""

import pytesseract
from pytesseract import Output
import PyPDF2
from pathlib import Path
from PIL import Image
import logging
from typing import Tuple, Dict, Optional
from pydantic import BaseModel
pytesseract.pytesseract.tesseract_cmd = r"C:\Users\22600011\smalter-autodoc\tools\tesseract\tesseract.exe"
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# MODÈLES PYDANTIC (Structures de Données)
# ══════════════════════════════════════════════════════════════════

class OCRQualityScore(BaseModel):
    """Score de qualité OCR (seulement pour images)"""
    overall: float              # Score global 0-100
    confidence: float           # Confiance moyenne Tesseract
    recognition_rate: float     # % caractères reconnus
    text_coherence: float       # Présence mots français
    threshold: float = 70.0     # Seuil acceptation
    passed: bool                # True si >= threshold

class TextExtractionResult(BaseModel):
    """Résultat extraction texte"""
    text: str                              # Texte brut extrait
    extraction_method: str                 # "DIRECT" ou "OCR"
    char_count: int                        # Nombre caractères
    word_count: int                        # Nombre mots
    ocr_quality: Optional[OCRQualityScore] = None  # Seulement si OCR
    metadata: Dict = {}                    # Infos supplémentaires

# ══════════════════════════════════════════════════════════════════
# CLASSE PRINCIPALE
# ══════════════════════════════════════════════════════════════════

class OCREngine:
    """
    Moteur extraction texte avec deux stratégies
    
    Utilisation:
        >>> engine = OCREngine()
        >>> 
        >>> # PDF natif
        >>> result = engine.extract_from_pdf_native("facture.pdf")
        >>> print(result.extraction_method)  # "DIRECT"
        >>> 
        >>> # Image
        >>> result = engine.extract_from_image("facture.jpg")
        >>> print(result.extraction_method)  # "OCR"
    """
    
    def __init__(
        self,
        tesseract_lang: str = "fra",      # Langue OCR (français)
        min_ocr_confidence: float = 70.0  # Seuil confiance min
    ):
        self.tesseract_lang = tesseract_lang
        self.min_ocr_confidence = min_ocr_confidence
        
        logger.info(
            f"OCREngine initialisé "
            f"(Lang: {tesseract_lang}, Min Confidence: {min_ocr_confidence}%)"
        )
    
    # ══════════════════════════════════════════════════════════════
    # MÉTHODE 1 : EXTRACTION DIRECTE (PDF Natif)
    # ══════════════════════════════════════════════════════════════
    
    def extract_from_pdf_native(self, pdf_path: str | Path) -> TextExtractionResult:
        """
        Extrait texte d'un PDF natif (sans OCR)
        
        Avantages:
        - Précision 100% (pas d'erreur de reconnaissance)
        - Rapide (0.5s vs 3-5s pour OCR)
        - Préserve structure (espaces, retours ligne)
        
        Args:
            pdf_path: Chemin vers PDF
            
        Returns:
            TextExtractionResult avec method="DIRECT"
        """
        pdf_path = Path(pdf_path)
        
        try:
            logger.info(f"Extraction DIRECTE: {pdf_path.name}")
            
            # Ouvrir PDF avec PyPDF2
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                # Nombre de pages
                num_pages = len(pdf_reader.pages)
                
                # ═══════════════════════════════════════════════
                # EXTRACTION PAGE PAR PAGE
                # ═══════════════════════════════════════════════
                # On concatène le texte de toutes les pages
                
                all_text = ""
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    
                    # Ajouter séparateur entre pages
                    if page_num > 0:
                        all_text += "\n\n--- Page {} ---\n\n".format(page_num + 1)
                    
                    all_text += page_text
            
            # ═══════════════════════════════════════════════
            # STATISTIQUES
            # ═══════════════════════════════════════════════
            
            char_count = len(all_text)
            word_count = len(all_text.split())
            
            logger.info(
                f"✅ Extraction réussie: {char_count} chars, "
                f"{word_count} mots, {num_pages} pages"
            )
            
            return TextExtractionResult(
                text=all_text,
                extraction_method="DIRECT",
                char_count=char_count,
                word_count=word_count,
                ocr_quality=None,  # Pas d'OCR = pas de score qualité
                metadata={
                    "pages": num_pages,
                    "source": "PyPDF2"
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur extraction PDF: {str(e)}", exc_info=True)
            raise
    
    # ══════════════════════════════════════════════════════════════
    # MÉTHODE 2 : OCR (Images et PDF Scans)
    # ══════════════════════════════════════════════════════════════
    
    def extract_from_image(self, image_path: str | Path) -> TextExtractionResult:
        """
        Extrait texte d'une image avec OCR Tesseract
        
        Processus:
        1. OCR avec scores de confiance par mot
        2. Calcul score qualité global
        3. Validation seuil minimum
        
        Args:
            image_path: Chemin vers image (JPG/PNG) ou page extraite de PDF
            
        Returns:
            TextExtractionResult avec method="OCR"
            
        Raises:
            ValueError: Si qualité OCR < seuil
        """
        image_path = Path(image_path)
        
        try:
            logger.info(f"Extraction OCR: {image_path.name}")
            
            # Charger image
            image = Image.open(image_path)
            
            # ═══════════════════════════════════════════════
            # OCR AVEC SCORES DE CONFIANCE
            # ═══════════════════════════════════════════════
            # pytesseract.image_to_data() retourne un dict avec:
            # - 'text': Mots reconnus
            # - 'conf': Score confiance par mot (0-100)
            # - 'left', 'top', 'width', 'height': Positions
            
            ocr_data = pytesseract.image_to_data(
                image,
                lang=self.tesseract_lang,
                output_type=Output.DICT,
                config='--oem 3 --psm 6'  # OEM=LSTM, PSM=Block uniform
            )
            
            # ═══════════════════════════════════════════════
            # EXTRAIRE TEXTE BRUT (méthode simple)
            # ═══════════════════════════════════════════════
            
            text_simple = pytesseract.image_to_string(
                image,
                lang=self.tesseract_lang,
                config='--oem 3 --psm 6'
            )
            
            # ═══════════════════════════════════════════════
            # CALCULER SCORE QUALITÉ OCR
            # ═══════════════════════════════════════════════
            
            ocr_quality = self._calculate_ocr_quality(ocr_data, text_simple)
            
            # ═══════════════════════════════════════════════
            # VÉRIFIER SEUIL MINIMUM
            # ═══════════════════════════════════════════════
            
            if not ocr_quality.passed:
                logger.warning(
                    f"⚠️ Qualité OCR insuffisante: {ocr_quality.overall:.1f}% "
                    f"< {self.min_ocr_confidence}%"
                )
                # On ne rejette pas ici, on laisse l'API décider
            
            # ═══════════════════════════════════════════════
            # STATISTIQUES
            # ═══════════════════════════════════════════════
            
            char_count = len(text_simple)
            word_count = len(text_simple.split())
            
            logger.info(
                f"✅ OCR terminé: {char_count} chars, {word_count} mots, "
                f"Qualité: {ocr_quality.overall:.1f}%"
            )
            
            return TextExtractionResult(
                text=text_simple,
                extraction_method="OCR",
                char_count=char_count,
                word_count=word_count,
                ocr_quality=ocr_quality,
                metadata={
                    "tesseract_lang": self.tesseract_lang,
                    "confidence_avg": ocr_quality.confidence
                }
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur OCR: {str(e)}", exc_info=True)
            raise
    
    # ══════════════════════════════════════════════════════════════
    # MÉTHODE PRIVÉE : CALCUL QUALITÉ OCR
    # ══════════════════════════════════════════════════════════════
    
    def _calculate_ocr_quality(
        self, 
        ocr_data: Dict, 
        text: str
    ) -> OCRQualityScore:
        """
        Calcule score qualité OCR
        
        Critères:
        1. Confiance moyenne (scores Tesseract)
        2. Taux reconnaissance (% chars valides)
        3. Cohérence texte (présence mots français)
        """
        
        # ═══════════════════════════════════════════════
        # 1. CONFIANCE MOYENNE
        # ═══════════════════════════════════════════════
        # Tesseract donne un score 0-100 par mot
        # -1 = pas de détection
        
        confidences = [
            float(conf) 
            for conf in ocr_data['conf'] 
            if conf != '-1'  # Ignorer non-détections
        ]
        
        if not confidences:
            # Aucun mot détecté = OCR raté
            return OCRQualityScore(
                overall=0.0,
                confidence=0.0,
                recognition_rate=0.0,
                text_coherence=0.0,
                passed=False
            )
        
        avg_confidence = sum(confidences) / len(confidences)
        
        # Ratio mots haute confiance (>80%)
        high_conf_ratio = sum(1 for c in confidences if c >= 80) / len(confidences)
        
        confidence_score = avg_confidence * 0.7 + high_conf_ratio * 100 * 0.3
        
        # ═══════════════════════════════════════════════
        # 2. TAUX RECONNAISSANCE
        # ═══════════════════════════════════════════════
        # % caractères alphanumériques vs symboles parasites
        
        if not text.strip():
            recognition_rate = 0.0
        else:
            alnum_chars = sum(c.isalnum() or c.isspace() for c in text)
            total_chars = len(text)
            alnum_ratio = alnum_chars / total_chars
            
            # Détecter symboles parasites (###, ***)
            import re
            parasites = len(re.findall(r'#{3,}|\*{3,}|\|{3,}', text))
            
            recognition_rate = (alnum_ratio * 100) - min(30, parasites * 10)
            recognition_rate = max(0.0, recognition_rate)
        
        # ═══════════════════════════════════════════════
        # 3. COHÉRENCE TEXTE
        # ═══════════════════════════════════════════════
        # Présence de mots français courants
        
        common_words = [
            'le', 'la', 'de', 'et', 'un', 'une', 'du', 'des',
            'total', 'montant', 'date', 'facture', 'client',
            'fournisseur', 'ttc', 'tva', 'ht'
        ]
        
        text_lower = text.lower()
        words_found = sum(1 for word in common_words if word in text_lower)
        coherence_score = (words_found / len(common_words)) * 100
        
        # ═══════════════════════════════════════════════
        # SCORE GLOBAL (Moyenne pondérée)
        # ═══════════════════════════════════════════════
        
        overall = (
            confidence_score * 0.4 +
            recognition_rate * 0.4 +
            coherence_score * 0.2
        )
        
        passed = overall >= self.min_ocr_confidence
        
        logger.debug(
            f"Qualité OCR: Overall={overall:.1f}% "
            f"(Conf={confidence_score:.1f}, "
            f"Recog={recognition_rate:.1f}, "
            f"Coher={coherence_score:.1f})"
        )
        
        return OCRQualityScore(
            overall=round(overall, 2),
            confidence=round(confidence_score, 2),
            recognition_rate=round(recognition_rate, 2),
            text_coherence=round(coherence_score, 2),
            threshold=self.min_ocr_confidence,
            passed=passed
        )