# src/smalter_autodoc/api/main.py
from fastapi import FastAPI, Form, UploadFile, File, HTTPException
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
from src.smalter_autodoc.core.document_router import DocumentRouter
from src.smalter_autodoc.core.agents.base_agent import ProcessingResult
from src.smalter_autodoc.core.document_type_validator import DocumentTypeValidator


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


document_router = DocumentRouter(use_llm=True, language='fr')

document_type_validator = DocumentTypeValidator()





@app.post("/api/v1/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), document_type: str = Form(...), language: str = Form('auto')):
    """
    Upload et traitement complet d'un document
    
    Workflow complet :
    1. Validation fichier (extension, taille)
    2. Sauvegarde temporaire
    3. PORTE 0 : Détection type fichier (PDF/Image)
    4. PORTE 1 : Qualité image (si nécessaire)
    5. PORTE 2 : Extraction texte (OCR ou direct)
    6. PORTE 3 : Sélection agent selon document_type
    7. PORTE 4 : Extraction structurée (Regex + LLM)
    8. PORTE 5 : Validation agent (champs obligatoires)
    
    Args:
        file: Fichier uploadé (PDF, JPG, PNG)
        document_type: Type déclaré ("FACTURE", "RELEVE_BANCAIRE", "TICKET_Z")
    
    Returns:
        UploadResponse avec données extraites ou raison du rejet
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
        image_to_check = None
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
        # PORTE 2A : EXTRACTION TEXTE
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
        # PORTE 2B : VALIDATION SUBSTANTIALITÉ TEXTE
        # ══════════════════════════════════════════════════════════════════

        logger.info(f"Document {document_id}: 🚪 PORTE 2B - Validation substantialité")

        text_length = len(text_extraction_result.text.strip())

        # Vérifier si texte substantiel
        if text_length < 50:
            logger.warning(
                f"⚠️ Texte trop court ({text_length} chars). "
                f"Contenu : '{text_extraction_result.text[:100]}'"  # ← LOG le texte
            )
            
            # Si PDF natif avec peu de texte → Convertir en image et OCR
            if file_type == FileType.PDF_NATIVE_TEXT:
                logger.info("🔄 Tentative conversion PDF → Image pour OCR complet")
                
                try:
                    # Convertir première page en image
                    image_path = pdf_converter.convert_first_page(
                        temp_path,
                        settings.PROCESSED_DIR
                    )
                    
                    logger.info(f"✅ Image extraite : {image_path}")  # ← Vérifier chemin
                    
                    # OCR sur l'image
                    new_text_result = ocr_engine.extract_from_image(image_path)
                    
                    logger.info(
                        f"✅ OCR terminé : {new_text_result.char_count} chars extraits\n"
                        f"Preview : {new_text_result.text[:200]}"  # ← LOG preview
                    )
                    
                    # ════════════════════════════════════════════════════
                    # IMPORTANT : Vérifier que OCR a vraiment extrait du texte
                    # ════════════════════════════════════════════════════
                    
                    if new_text_result.char_count > text_length:
                        # OCR a extrait plus de texte → Remplacer
                        text_extraction_result = new_text_result
                        logger.info(
                            f"✅ Texte mis à jour : {text_length} → {new_text_result.char_count} chars"
                        )
                    else:
                        logger.warning(
                            f"⚠️ OCR n'a pas amélioré l'extraction "
                            f"({new_text_result.char_count} chars)"
                        )
                    
                    # Nettoyer image temporaire
                    if image_path.exists():
                        image_path.unlink()
                        logger.debug("🗑️ Image temporaire supprimée")
                
                except Exception as e:
                    logger.error(f"❌ Erreur conversion/OCR : {e}", exc_info=True)  # ← Full traceback
                    
                    # Nettoyer
                    temp_path.unlink()
                    
                    return UploadResponse(
                        document_id=document_id,
                        status=ProcessingStatus.REJECTED,
                        rejected_at_gate=2,
                        rejection_reason="TEXT_EXTRACTION_FAILED",
                        file_type=file_type,
                        message=f"Texte insuffisant ({text_length} chars) et conversion échouée : {str(e)}",
                        suggestions=[
                            "Le document ne contient pas assez de texte exploitable",
                            "Vérifiez que le scan est complet",
                            "Essayez de rescanner le document en meilleure qualité",
                            f"Erreur technique : {str(e)}"  # ← Détail erreur
                        ],
                        metadata=file_metadata
                    )

        # Vérifier si texte = watermark connu
        if text_length < 100:
            watermarks = [
                'onlinephotoscanner', 'camscanner', 'adobe scan',
                'evaluation', 'demo', 'trial'
            ]
            
            text_lower = text_extraction_result.text.lower()
            
            if any(wm in text_lower for wm in watermarks):
                logger.warning(f"🚨 Watermark détecté : {text_lower}")
                
                # Même logique de conversion si pas déjà fait
                if file_type == FileType.PDF_NATIVE_TEXT and text_length < 100:
                    logger.info("🔄 Watermark détecté → Force OCR complet")
                    
                    try:
                        image_path = pdf_converter.convert_first_page(
                            temp_path,
                            settings.PROCESSED_DIR
                        )
                        
                        new_text_result = ocr_engine.extract_from_image(image_path)
                        
                        if new_text_result.char_count > text_length:
                            text_extraction_result = new_text_result
                            logger.info(
                                f"✅ Après OCR forcé : {new_text_result.char_count} chars"
                            )
                        
                        if image_path.exists():
                            image_path.unlink()
                            
                    except Exception as e:
                        logger.error(f"❌ Erreur OCR forcé watermark : {e}", exc_info=True)

        # ════════════════════════════════════════════════════════════════════
        # VÉRIFICATION FINALE : Si texte toujours < 50 chars → REJET
        # ════════════════════════════════════════════════════════════════════

        final_text_length = len(text_extraction_result.text.strip())

        if final_text_length < 50:
            logger.error(
                f"❌ REJET : Texte final insuffisant ({final_text_length} chars)\n"
                f"Contenu : '{text_extraction_result.text}'"
            )
            
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
                message=f"Document ne contient pas assez de texte exploitable ({final_text_length} chars)",
                suggestions=[
                    "Le document semble vide ou contenir seulement un watermark",
                    "Vérifiez que le fichier PDF contient bien une image scannée",
                    "Essayez d'exporter le scan dans un format image (JPG/PNG) plutôt que PDF",
                    "Rescannez le document original en meilleure qualité"
                ],
                metadata={
                    **file_metadata,
                    "extracted_text": text_extraction_result.text[:200],
                    "text_length": final_text_length
                }
            )

        logger.info(
            f"✅ Texte final validé : {final_text_length} chars\n"
            f"Preview : {text_extraction_result.text[:200]}"
        )







        # ══════════════════════════════════════════════════════
        # PORTE 3 : Validation Type Document
        # ══════════════════════════════════════════════════════
    
        logger.info(f"Document {document_id}: 🚪 PORTE 3A - Validation type document")
        
        type_validation = document_type_validator.validate(
            text_extraction_result.text,
            document_type
        )
        
        if not type_validation["valid"]:
            # Nettoyage
            temp_path.unlink()
            if image_to_check and image_to_check != temp_path:
                image_to_check.unlink()
            
            return UploadResponse(
                document_id=document_id,
                status=ProcessingStatus.REJECTED,
                rejected_at_gate=3,
                rejection_reason="TYPE_MISMATCH",
                file_type=file_type,
                message=type_validation["reason"],
                suggestions=[
                    f"Type détecté : {type_validation['detected_type']}",
                    f"Type déclaré : {type_validation['declared_type']}",
                    "Vérifiez le type de document avant de le soumettre à nouveau"
                ],
                metadata={
                    **file_metadata,
                    "type_validation": type_validation
                }
            )
        
        # ══════════════════════════════════════════════════════
        # DÉTECTION LANGUE (si auto)
        # ══════════════════════════════════════════════════════
        if language == 'auto':
            # Auto-détection depuis texte
            from src.smalter_autodoc.core.extractors.pattern_manager import PatternManager
            pattern_manager = PatternManager.from_text(text_extraction_result.text)
            detected_language = pattern_manager.patterns.LANGUAGE_CODE
            logger.info(f"Langue auto-détectée : {detected_language}")
        else:
            detected_language = language.lower()
        
        document_router = DocumentRouter(use_llm=True, language=detected_language)
    


        # ══════════════════════════════════════════════════════
        # 6. PORTE 3 : Sélection Agent
        # ══════════════════════════════════════════════════════
        
        logger.info(f"Document {document_id}: 🚪 PORTE 3 - Sélection agent")
        
        agent = document_router.get_agent(document_type)
        
        
        if not agent:
            temp_path.unlink()
            if image_to_check and image_to_check != temp_path:
                image_to_check.unlink()
            
            return UploadResponse(
                document_id=document_id,
                status=ProcessingStatus.REJECTED,
                rejected_at_gate=3,
                rejection_reason="UNKNOWN_DOCUMENT_TYPE",
                file_type=file_type,
                message=f"Type de document non supporté: '{document_type}'",
                suggestions=[
                    f"Types supportés : {', '.join(document_router.list_supported_types())}"
                ],
                metadata=file_metadata
            )
        
        logger.info(f"Document {document_id}: Agent sélectionné = {agent.agent_name}")



        # ══════════════════════════════════════════════════════
        # 7-8. PORTE 4+5 : Extraction + Validation
        # ══════════════════════════════════════════════════════
        
        logger.info(f"Document {document_id}: 🚪 PORTE 4-5 - Extraction structurée + Validation")
        
        processing_result: ProcessingResult = agent.process(text_extraction_result.text)
        
        # ══════════════════════════════════════════════════════
        # SUCCÈS OU ÉCHEC
        # ══════════════════════════════════════════════════════
        
        # Nettoyer fichiers temporaires
        temp_path.unlink()
        if image_to_check and image_to_check != temp_path and image_to_check.exists():
            image_to_check.unlink()
        
        if processing_result.success:
            logger.info(f"Document {document_id}: ✅ Traitement réussi")
            
            return UploadResponse(
                document_id=document_id,
                status=ProcessingStatus.COMPLETED,
                file_type=file_type,
                quality_score=quality_score.dict() if quality_score else None,
                message=f"Document traité avec succès (confiance: {processing_result.confidence_score}%)",
                metadata={
                    **file_metadata,
                    'text_extraction': {
                        'method': text_extraction_result.extraction_method,
                        'char_count': text_extraction_result.char_count,
                    },
                    'agent': {
                        'name': processing_result.agent_name,
                        'document_type': processing_result.document_type,
                        'extraction_method': processing_result.extraction_method,
                        'confidence': processing_result.confidence_score,
                    },
                    'extracted_data': processing_result.extracted_data,
                }
            )
        
        else:
            logger.warning(f"Document {document_id}: ⚠️ Validation échouée")
            
            return UploadResponse(
                document_id=document_id,
                status=ProcessingStatus.REJECTED,
                rejected_at_gate=5,
                rejection_reason="VALIDATION_FAILED",
                file_type=file_type,
                quality_score=quality_score.dict() if quality_score else None,
                message="Validation échouée : champs obligatoires manquants",
                suggestions=processing_result.errors + processing_result.warnings,
                metadata={
                    **file_metadata,
                    'agent': {
                        'name': processing_result.agent_name,
                        'confidence': processing_result.confidence_score,
                    },
                    'extracted_data': processing_result.extracted_data,
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur fatale: {str(e)}", exc_info=True)
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