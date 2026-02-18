# src/smalter_autodoc/api/main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pathlib import Path
import shutil
import uuid
import logging

from src.smalter_autodoc.core.file_type_detector import FileTypeDetector, FileType
from src.smalter_autodoc.core.image_quality_checker import ImageQualityChecker
from src.smalter_autodoc.utils.config import settings
from src.smalter_autodoc.models.responses import UploadResponse, ProcessingStatus
from src.smalter_autodoc.core.pdf_to_image_converter import PDFToImageConverter
from src.smalter_autodoc.core.ocr_engine import OCREngine

# Setup logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize app
app = FastAPI(
    title="Smalter OCR API",
    version="0.1.0",
    description="Système OCR avec validation stricte"
)

# Initialize components
file_detector = FileTypeDetector()

quality_checker = ImageQualityChecker(
    min_overall=settings.MIN_IMAGE_QUALITY_SCORE
)

ocr_engine = OCREngine(tesseract_lang="fra", min_ocr_confidence=70.0)




@app.post("/api/v1/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload et analyse initiale d'un document
    
    Étapes:
    1. Validation fichier
    2. Sauvegarde temporaire
    3. Porte 0: Détection type
    4. Porte 1: Qualité image (si nécessaire)
    
    Returns:
        UploadResponse avec status et détails
    """
    document_id = str(uuid.uuid4())
    
    try:
        # 1. Valider extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Extension {file_ext} non supportée. "
                       f"Accepté: {settings.ALLOWED_EXTENSIONS}"
            )
        
        # 2. Valider taille
        file.file.seek(0, 2)  # Fin fichier
        file_size = file.file.tell()
        file.file.seek(0)  # Retour début
        
        if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"Fichier trop volumineux: {file_size/1024/1024:.1f}MB. "
                       f"Max: {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        # 3. Sauvegarder temporairement
        temp_path = settings.UPLOAD_DIR / f"{document_id}_{file.filename}"
        
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Document {document_id} uploadé: {file.filename} ({file_size} bytes)")
        
        # 4. PORTE 0: Détection type fichier
        file_type, file_metadata = file_detector.detect(str(temp_path))
        
        if file_type == FileType.UNSUPPORTED:
            # Nettoyer
            temp_path.unlink()
            
            return UploadResponse(
                document_id=document_id,
                status=ProcessingStatus.REJECTED,
                rejected_at_gate=0,
                rejection_reason="UNSUPPORTED_FILE_TYPE",
                file_type=file_type,
                message="Type de fichier non supporté",
                metadata=file_metadata
            )
        
        logger.info(f"Document {document_id}: Type détecté = {file_type}")
        
       # 5. PORTE 1: Qualité image (SEULEMENT pour images)
        quality_score = None
        image_to_check = None  # ← Nouvelle variable
        pdf_converter = PDFToImageConverter(default_dpi=300)

        if file_type in [FileType.PDF_IMAGE, FileType.IMAGE_PURE]:
            
            # ════════════════════════════════════════════════════════════
            # Si PDF scan → Convertir en image d'abord
            # ════════════════════════════════════════════════════════════
            if file_type == FileType.PDF_IMAGE:
                try:
                    logger.info(f"Document {document_id}: Conversion PDF → Image")
                    
                    image_to_check = pdf_converter.convert_first_page(
                        temp_path, 
                        settings.PROCESSED_DIR
                    )
                    
                    logger.info(f"Document {document_id}: Image extraite → {image_to_check.name}")
                    
                except Exception as e:
                    logger.error(f"Erreur conversion PDF: {str(e)}")
                    
                    # Nettoyer
                    temp_path.unlink()
                    
                    return UploadResponse(
                        document_id=document_id,
                        status=ProcessingStatus.REJECTED,
                        rejected_at_gate=1,
                        rejection_reason="PDF_CONVERSION_FAILED",
                        file_type=file_type,
                        message=f"Impossible d'extraire l'image du PDF: {str(e)}",
                        metadata=file_metadata
                    )
            else:
                # Image pure → Pas de conversion nécessaire
                image_to_check = temp_path
            
            # ════════════════════════════════════════════════════════════
            # Vérifier qualité de l'image
            # ════════════════════════════════════════════════════════════
            quality_score = quality_checker.check_quality(image_to_check)
            
            if not quality_score.passed:
                # Nettoyer les fichiers temporaires
                temp_path.unlink()
                if image_to_check != temp_path and image_to_check.exists():
                    image_to_check.unlink()  # Supprimer image extraite aussi
                
                return UploadResponse(
                    document_id=document_id,
                    status=ProcessingStatus.REJECTED,
                    rejected_at_gate=1,
                    rejection_reason="IMAGE_QUALITY_LOW",
                    file_type=file_type,
                    quality_score=quality_score.dict(),
                    message=f"Qualité image insuffisante: {quality_score.overall}%",
                    suggestions=quality_score.suggestions,
                    metadata=file_metadata
                )
            

        # ══════════════════════════════════════════════════════════════════
        # PORTE 2 : EXTRACTION TEXTE
        # ══════════════════════════════════════════════════════════════════

        logger.info(f"Document {document_id}: 🚪 PORTE 2 - Extraction texte")

        text_extraction_result = None

        try:
            if file_type == FileType.PDF_NATIVE_TEXT:
                # ═══════════════════════════════════════════════════════════
                # Cas 1 : PDF Natif → Extraction directe
                # ═══════════════════════════════════════════════════════════
                    
                text_extraction_result = ocr_engine.extract_from_pdf_native(temp_path)
                    
                logger.info(
                    f"Document {document_id}: "
                    f"Extraction DIRECTE réussie "
                    f"({text_extraction_result.char_count} chars)"
                )
                
            elif file_type in [FileType.PDF_IMAGE, FileType.IMAGE_PURE]:
                # ═══════════════════════════════════════════════════════════
                # Cas 2 : Image ou PDF Scan → OCR
                # ═══════════════════════════════════════════════════════════
                    
                # Image à traiter (déjà extraite à la Porte 1)
                text_extraction_result = ocr_engine.extract_from_image(image_to_check)
                    
                logger.info(
                    f"Document {document_id}: "
                    f"OCR réussi "
                    f"({text_extraction_result.char_count} chars, "
                    f"Qualité: {text_extraction_result.ocr_quality.overall:.1f}%)"
                )
                    
                # ═══════════════════════════════════════════════════════════
                # Vérifier qualité OCR
                # ═══════════════════════════════════════════════════════════
                    
                if not text_extraction_result.ocr_quality.passed:
                    # Nettoyer fichiers
                    temp_path.unlink()
                    if image_to_check != temp_path and image_to_check.exists():
                        image_to_check.unlink()
                        
                    return UploadResponse(
                        document_id=document_id,
                        status=ProcessingStatus.REJECTED,
                        rejected_at_gate=2,
                        rejection_reason="OCR_QUALITY_LOW",
                        file_type=file_type,
                        quality_score=quality_score.dict() if quality_score else None,
                        message=f"Qualité OCR insuffisante: {text_extraction_result.ocr_quality.overall:.1f}%",
                        suggestions=[
                            "📄 Le texte du document est difficile à lire. Recommandations:",
                            "- Améliorer la qualité du scan (netteté, résolution)",
                            "- Vérifier que le document n'est pas trop dégradé",
                            "- Réessayer avec un document de meilleure qualité"
                        ],
                        metadata={
                            **file_metadata,
                            'ocr_quality': text_extraction_result.ocr_quality.dict()
                        }
                    )

        except Exception as e:
            logger.error(f"Document {document_id}: Erreur extraction texte: {str(e)}", exc_info=True)
                
            # Nettoyer
            temp_path.unlink()
            if image_to_check and image_to_check != temp_path and image_to_check.exists():
                image_to_check.unlink()
                
            return UploadResponse(
                document_id=document_id,
                status=ProcessingStatus.REJECTED,
                rejected_at_gate=2,
                rejection_reason="TEXT_EXTRACTION_FAILED",
                file_type=file_type,
                message=f"Impossible d'extraire le texte: {str(e)}",
                metadata=file_metadata
            )

        # ══════════════════════════════════════════════════════════════════
        # SUCCÈS : Document accepté avec texte extrait
        # ══════════════════════════════════════════════════════════════════

        logger.info(
            f"Document {document_id}: ✅ Toutes portes passées "
            f"(Type: {file_type}, Méthode: {text_extraction_result.extraction_method})"
        )

        return UploadResponse(
            document_id=document_id,
            status=ProcessingStatus.PENDING,
            file_type=file_type,
            quality_score=quality_score.dict() if quality_score else None,
            message="Document accepté, texte extrait avec succès",
            metadata={
                **file_metadata,
                'text_extraction': {
                    'method': text_extraction_result.extraction_method,
                    'char_count': text_extraction_result.char_count,
                    'word_count': text_extraction_result.word_count,
                    'text_preview': text_extraction_result.text[:200] + "..." if len(text_extraction_result.text) > 200 else text_extraction_result.text,
                    'ocr_quality': text_extraction_result.ocr_quality.dict() if text_extraction_result.ocr_quality else None
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur upload {document_id}: {str(e)}", exc_info=True)
        
        # Nettoyer si fichier créé
        if temp_path.exists():
            temp_path.unlink()
        
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": "0.1.0",
        "components": {
            "file_detector": "active",
            "quality_checker": "active"
        }
    }