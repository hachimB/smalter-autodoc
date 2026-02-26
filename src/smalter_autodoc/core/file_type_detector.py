import magic  # python-magic pour détection MIME
import PyPDF2
from PIL import Image
from typing import Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class FileType(str, Enum):
    """Types de fichiers supportés"""
    PDF_NATIVE_TEXT = "PDF_NATIVE_TEXT"  # PDF avec texte extractible
    PDF_IMAGE = "PDF_IMAGE"               # PDF de scan (image)
    IMAGE_PURE = "IMAGE_PURE"             # JPG/PNG direct
    UNSUPPORTED = "UNSUPPORTED"           # Autre format

class FileTypeDetector:
    """
    Détecte le type exact de fichier pour router vers le bon traitement
    
    Méthodes de détection:
    1. Extension (.pdf, .jpg, .png)
    2. Magic bytes (signature fichier)
    3. Pour PDF: Présence de texte natif
    """
    
    SUPPORTED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.tiff', '.bmp'}
    SUPPORTED_PDF_EXTENSION = '.pdf'
    
    def detect(self, file_path: str) -> Tuple[FileType, dict]:
        """
        Détecte le type de fichier
        
        Args:
            file_path: Chemin vers le fichier
            
        Returns:
            (FileType, metadata dict)
            
        Exemple:
            >>> detector = FileTypeDetector()
            >>> file_type, meta = detector.detect("facture.pdf")
            >>> print(file_type)
            FileType.PDF_NATIVE_TEXT
            >>> print(meta)
            {'pages': 1, 'has_text': True, 'text_ratio': 0.85}
        """
        try:
            # 1. Vérifier extension
            import os
            ext = os.path.splitext(file_path)[1].lower()
            
            # 2. Vérifier type MIME avec magic bytes
            mime_type = magic.from_file(file_path, mime=True)
            
            logger.info(f"Fichier: {file_path}, Extension: {ext}, MIME: {mime_type}")
            
            # 3. Router selon type
            if mime_type == 'application/pdf':
                return self._analyze_pdf(file_path)
            
            elif mime_type.startswith('image/'):
                return self._analyze_image(file_path)
            
            else:
                logger.warning(f"Type non supporté: {mime_type}")
                return FileType.UNSUPPORTED, {
                    'mime_type': mime_type,
                    'reason': f'Format {mime_type} non pris en charge'
                }
                
        except Exception as e:
            logger.error(f"Erreur détection type fichier: {str(e)}")
            return FileType.UNSUPPORTED, {'error': str(e)}
        

    
    def _analyze_pdf(self, file_path: str) -> Tuple[FileType, dict]:
        """
        Analyse un PDF pour déterminer s'il contient du texte natif ou des images
        
        Méthode:
        1. Ouvrir le PDF avec PyPDF2
        2. Extraire le texte de chaque page
        3. Calculer ratio texte/total caractères
        4. Si ratio > 10% → PDF natif, sinon → PDF image
        
        Justification seuil 10%:
        - PDF natif: Même avec peu de texte, ratio > 50%
        - PDF image: Quelques caractères parasites max, ratio < 5%
        """
        try:
            with open(file_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                
                num_pages = len(pdf_reader.pages)
                total_text = ""
                
                # Extraire texte de toutes les pages
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    total_text += page_text
                
                # Calculer ratio texte
                text_length = len(total_text.strip())
                total_chars = sum(1 for _ in total_text)
                text_ratio = text_length / max(total_chars, 1)
                
                logger.info(
                    f"PDF: {num_pages} pages, "
                    f"{text_length} caractères texte, "
                    f"ratio: {text_ratio:.2%}"
                )
                
                # Décision
                if text_ratio > 0.10:  # 10% de texte extractible
                    file_type = FileType.PDF_NATIVE_TEXT
                    has_text = True
                else:
                    file_type = FileType.PDF_IMAGE
                    has_text = False
                
                metadata = {
                    'pages': num_pages,
                    'has_text': has_text,
                    'text_length': text_length,
                    'text_ratio': round(text_ratio, 3),
                    'sample_text': total_text[:200] if has_text else None
                }
                
                return file_type, metadata
                
        except Exception as e:
            logger.error(f"Erreur analyse PDF: {str(e)}")
            return FileType.UNSUPPORTED, {'error': str(e)}
    
    def _analyze_image(self, file_path: str) -> Tuple[FileType, dict]:
        """
        Analyse une image (JPG, PNG)
        
        Vérifie:
        - Format supporté
        - Dimensions
        - Mode couleur
        """
        try:
            with Image.open(file_path) as img:
                width, height = img.size
                mode = img.mode
                format_name = img.format
                
                logger.info(
                    f"Image: {width}x{height}px, "
                    f"Mode: {mode}, "
                    f"Format: {format_name}"
                )
                
                metadata = {
                    'width': width,
                    'height': height,
                    'mode': mode,
                    'format': format_name,
                    'dpi': self._serialize_dpi(img.info.get('dpi'))
                }
                
                return FileType.IMAGE_PURE, metadata
                
        except Exception as e:
            logger.error(f"Erreur analyse image: {str(e)}")
            return FileType.UNSUPPORTED, {'error': str(e)}
    


    def _serialize_dpi(self, dpi_value) -> list:
        """
        Convertit DPI en format sérialisable
        
        Args:
            dpi_value: Peut être tuple, IFDRational, ou None
            
        Returns:
            Liste [dpi_x, dpi_y] ou [72, 72] par défaut
        """
        if dpi_value is None:
            return [72, 72]
        
        try:
            # Si tuple de IFDRational ou autres types
            if isinstance(dpi_value, (tuple, list)):
                return [float(x) for x in dpi_value[:2]]
            
            # Si valeur unique
            return [float(dpi_value), float(dpi_value)]
            
        except (TypeError, ValueError):
            logger.warning(f"DPI non-sérialisable: {type(dpi_value)}, utilisation valeur par défaut")
            return [72, 72]
