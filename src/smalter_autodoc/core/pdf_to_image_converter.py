from pdf2image import convert_from_path
from pathlib import Path
from PIL import Image
import logging
from typing import Optional

logger = logging.getLogger(__name__)

POPPLER_PATH = r"C:\Users\22600004\Downloads\Release-25.12.0-0\poppler-25.12.0\Library\bin"

class PDFToImageConverter:
    """
    Convertit PDF → Image pour analyse qualité
    """
    
    def __init__(self, default_dpi: int = 300):
        self.default_dpi = default_dpi
        logger.info(f"PDFToImageConverter initialisé (DPI: {default_dpi})")
    
    def convert_first_page(
        self, 
        pdf_path: str | Path,
        output_dir: Path,
        dpi: Optional[int] = None
    ) -> Path:
        """
        Extrait la première page d'un PDF en image JPG.
        """
        pdf_path = Path(pdf_path)
        dpi = dpi or self.default_dpi
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF introuvable: {pdf_path}")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"{pdf_path.stem}_page1.jpg"
        output_path = output_dir / output_filename
        
        try:
            logger.info(f"Conversion PDF → Image: {pdf_path.name} (DPI: {dpi})")
            
            # Convertir uniquement la première page
            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=1,
                last_page=1,
                fmt='jpeg',
                poppler_path=POPPLER_PATH
            )

            if not images:
                raise Exception("Aucune image extraite du PDF")
            
            # Copier l'image pour éviter le verrouillage Windows
            with images[0] as img:
                img_copy = img.copy()  # copie en mémoire
            # Fermer l'image originale explicitement
            images[0].close()
            
            # Sauver la copie
            img_copy.save(output_path, 'JPEG', quality=95, optimize=True)
            img_copy.close()  # ferme la copie

            return output_path
        
        except Exception as e:
            logger.error(f"❌ Erreur conversion PDF: {str(e)}", exc_info=True)
            raise

