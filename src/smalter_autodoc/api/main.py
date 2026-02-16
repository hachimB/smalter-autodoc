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
        
        # 3. Sauvegarder tempo rairement
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
            
            # 6. Succès jusqu'ici
            return UploadResponse(
                document_id=document_id,
                status=ProcessingStatus.PENDING,
                file_type=file_type,
                quality_score=quality_score.dict() if quality_score else None,
                message="Document accepté, en attente traitement OCR",
                metadata=file_metadata
            )
        return UploadResponse(
            document_id=document_id,
            status=ProcessingStatus.PENDING,
            file_type=file_type,
            quality_score=quality_score.dict() if quality_score else None,
            message="Document accepté, en attente traitement OCR",
            metadata=file_metadata
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