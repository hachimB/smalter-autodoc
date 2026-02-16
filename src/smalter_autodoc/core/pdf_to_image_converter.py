# src/smalter_autodoc/core/pdf_to_image_converter.py
"""
Convertisseur PDF → Image pour validation qualité

Objectif: Extraire la première page d'un PDF scan
pour pouvoir vérifier sa qualité image avant OCR
"""

from pdf2image import convert_from_path
from pathlib import Path
from PIL import Image
import logging
from typing import Optional

logger = logging.getLogger(__name__)

POPPLER_PATH = r"C:\Users\22600011\Downloads\Release-25.12.0-0\poppler-25.12.0\Library\bin" # poppler est indispensable pour utiliser pdf2image

class PDFToImageConverter:
    """
    Convertit PDF → Image pour analyse qualité
    
    Cas d'usage:
        PDF_IMAGE (scan) → Extraire image → Vérifier qualité → OCR
    """
    
    def __init__(self, default_dpi: int = 300):
        """
        Args:
            default_dpi: Résolution par défaut (300 = standard scanner)
        """
        self.default_dpi = default_dpi
        logger.info(f"PDFToImageConverter initialisé (DPI: {default_dpi})")
    
    def convert_first_page(
        self, 
        pdf_path: str | Path,
        output_dir: Path,
        dpi: Optional[int] = None
    ) -> Path:
        """
        Extrait la première page d'un PDF en image JPG
        
        Args:
            pdf_path: Chemin vers le PDF source
            output_dir: Dossier où sauvegarder l'image
            dpi: Résolution (utilise default_dpi si None)
            
        Returns:
            Path: Chemin vers l'image extraite (page1.jpg)
            
        Raises:
            FileNotFoundError: Si PDF n'existe pas
            Exception: Si conversion échoue
            
        Exemple:
            >>> converter = PDFToImageConverter()
            >>> image_path = converter.convert_first_page(
            ...     "facture_scan.pdf",
            ...     Path("data/processed")
            ... )
            >>> print(image_path)
            data/processed/facture_scan_page1.jpg
        """
        pdf_path = Path(pdf_path)
        dpi = dpi or self.default_dpi
        
        # Vérifier que le PDF existe
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF introuvable: {pdf_path}")
        
        # Créer dossier output si nécessaire
        output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            logger.info(f"Conversion PDF → Image: {pdf_path.name} (DPI: {dpi})")
            
            # ════════════════════════════════════════════════════════════
            # LIGNE CRITIQUE : Conversion PDF → Liste d'images
            # ════════════════════════════════════════════════════════════
            # convert_from_path() utilise Poppler (moteur PDF)
            # - first_page=1, last_page=1 → Seulement page 1
            # - dpi=300 → Résolution haute qualité
            # - fmt='jpeg' → Format sortie
            # Retourne: List[PIL.Image]
            
            images = convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=1,     # ← Commencer à page 1
                last_page=1,      # ← Arrêter à page 1
                fmt='jpeg',        # ← Format sortie
                poppler_path=POPPLER_PATH
            )
            
            # images[0] = PIL.Image de la page 1
            if not images:
                raise Exception("Aucune image extraite du PDF")
            
            page1_image = images[0]  # Première (et unique) page
            
            # ════════════════════════════════════════════════════════════
            # Construire nom fichier sortie
            # ════════════════════════════════════════════════════════════
            # facture_scan.pdf → facture_scan_page1.jpg
            
            output_filename = f"{pdf_path.stem}_page1.jpg"
            output_path = output_dir / output_filename
            
            # ════════════════════════════════════════════════════════════
            # Sauvegarder l'image
            # ════════════════════════════════════════════════════════════
            # quality=95 → Haute qualité JPG (95/100)
            # optimize=True → Compression optimisée
            
            page1_image.save(
                output_path,
                'JPEG',
                quality=95,      # ← Qualité maximale
                optimize=True    # ← Réduire taille sans perte
            )
            
            # Vérifier taille fichier créé
            file_size_mb = output_path.stat().st_size / (1024 * 1024)
            
            logger.info(
                f"✅ Image extraite: {output_path.name} "
                f"({page1_image.size[0]}×{page1_image.size[1]}px, "
                f"{file_size_mb:.2f}MB)"
            )
            
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Erreur conversion PDF: {str(e)}", exc_info=True)
            raise