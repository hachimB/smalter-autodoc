"""
Porte 1 : Vérification Qualité Image

Calcule 4 scores:
1. Résolution (DPI)
2. Netteté (Variance Laplacien)
3. Contraste (RMS)
4. Orientation (Angle rotation)

Score global = moyenne pondérée
Seuil acceptation : 75%
"""

import cv2
import numpy as np
from PIL import Image
from typing import Dict, List
from pathlib import Path
import logging
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class QualityScore(BaseModel):
    """Modèle résultat qualité image"""
    overall: float
    sharpness: float
    contrast: float
    resolution: float
    orientation: float
    threshold: float = 75.0
    passed: bool
    suggestions: List[str] = []

class ImageQualityChecker:
    """
    Vérifie la qualité d'une image AVANT traitement OCR
    
    Objectif: Rejeter images inexploitables pour économiser ressources
    
    Exemple:
        >>> checker = ImageQualityChecker()
        >>> score = checker.check_quality("facture.jpg")
        >>> if score.passed:
        ...     print(f"OK: {score.overall}%")
        ... else:
        ...     print(f"REJET: {score.suggestions}")
    """
    
    def __init__(
        self,
        min_dpi: int = 200,
        min_sharpness: float = 45.0,
        min_contrast: float = 35.0,
        min_overall: float = 70.0
    ):
        self.min_dpi = min_dpi
        self.min_sharpness = min_sharpness
        self.min_contrast = min_contrast
        self.min_overall = min_overall
    
    def check_quality(self, image_path: str | Path) -> QualityScore:
        """
        Point d'entrée principal : évalue qualité globale
        
        Returns:
            QualityScore avec détails par critère
        """
        try:
            image_path = Path(image_path)
            
            # Charger image
            img_cv = cv2.imread(str(image_path))
            img_pil = Image.open(image_path)
            
            if img_cv is None:
                logger.error(f"Impossible de charger: {image_path}")
                return QualityScore(
                    overall=0.0, sharpness=0.0, contrast=0.0,
                    resolution=0.0, orientation=0.0, passed=False,
                    suggestions=["❌ Fichier image corrompu ou illisible"]
                )
            
            # Calculer scores individuels
            resolution_score = self._check_resolution(img_pil)
            sharpness_score = self._check_sharpness(img_cv)
            contrast_score = self._check_contrast(img_cv)
            orientation_score = self._check_orientation(img_cv)
            
            # Score global (moyenne pondérée)
            overall = (
                sharpness_score * 0.4 +
                contrast_score * 0.3 +
                resolution_score * 0.2 +
                orientation_score * 0.1
            )
            
            passed = (overall >= self.min_overall) and (resolution_score >= 50.0)
            
            logger.info(
                f"Qualité {image_path.name}: "
                f"Overall={overall:.1f}% "
                f"(Sharp={sharpness_score:.1f}, "
                f"Contrast={contrast_score:.1f}, "
                f"Res={resolution_score:.1f}, "
                f"Orient={orientation_score:.1f}) "
                f"→ {'✅ PASSED' if passed else '❌ REJECTED'}"
            )
            
            # Générer suggestions si rejet
            suggestions = self._generate_suggestions(
                sharpness_score, contrast_score,
                resolution_score, orientation_score
            ) if not passed else []
            
            return QualityScore(
                overall=round(overall, 2),
                sharpness=round(sharpness_score, 2),
                contrast=round(contrast_score, 2),
                resolution=round(resolution_score, 2),
                orientation=round(orientation_score, 2),
                threshold=self.min_overall,
                passed=passed,
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"Erreur check_quality: {str(e)}", exc_info=True)
            return QualityScore(
                overall=0.0, sharpness=0.0, contrast=0.0,
                resolution=0.0, orientation=0.0, passed=False,
                suggestions=[f"❌ Erreur technique: {str(e)}"]
            )
    
    def _check_resolution(self, img: Image.Image) -> float:
        """
        Vérifie résolution image
        
        Formule:
        - ≥ 300 DPI (2480px pour A4) → 100%
        - 200-299 DPI → 50-99%
        - < 200 DPI → 0-49%
        """
        width, height = img.size
        dpi = img.info.get('dpi', (72, 72))[0]
        
        # Pour A4 (210×297mm):
        # 300 DPI = 2480×3508 px
        # 200 DPI = 1654×2339 px
        min_dimension = min(width, height)

        if min_dimension >= 2480:          # 300 DPI
            score = 100.0
        elif min_dimension >= 2067:        # 250 DPI
            score = 85.0 + (min_dimension - 2067) / (2480 - 2067) * 15.0
        elif min_dimension >= 1654:        # 200 DPI
            score = 50.0 + (min_dimension - 1654) / (2067 - 1654) * 35.0
        else:
            score = max(0.0, (min_dimension / 1654) * 50.0)
        
        logger.debug(
            f"Résolution: {width}×{height}px, "
            f"DPI={dpi}, Score={score:.1f}%"
        )
        
        return min(100.0, score)
    
    def _check_sharpness(self, img: np.ndarray) -> float:
        """
        Détecte flou avec opérateur de Laplace
        
        Principe:
        - Image nette → Beaucoup de contours → Variance élevée
        - Image floue → Peu de contours → Variance faible
        
        Formule:
        variance = Var(Laplacian(grayscale))
        
        Seuils empiriques:
        - variance > 150 → 100% (très net)
        - variance < 10 → 0% (très flou)
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()
        
        if variance >= 180:
            score = 100.0
        elif variance >= 40:
            score = 30.0 + (variance - 40) / (180 - 40) * 70.0
        else:
            score = max(0.0, variance / 40.0 * 30.0)
        
        
        logger.debug(f"Netteté: Variance Laplacien={variance:.2f}, Score={score:.1f}%")
        
        return max(0.0, min(100.0, score))
    
    def _check_contrast(self, img: np.ndarray) -> float:
        """
        Mesure contraste avec méthode RMS
        
        Formule:
        RMS = sqrt(mean((pixel - mean_pixel)²))
        
        Plus RMS élevé → Meilleur contraste
        
        Seuils:
        - RMS > 55 → 100%
        - RMS < 25 → 0%
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mean_intensity = np.mean(gray)
        rms_contrast = np.sqrt(np.mean((gray - mean_intensity) ** 2))
        
        if rms_contrast >= 55:
            score = 100.0
        elif rms_contrast >= 25:
            score = 40.0 + (rms_contrast - 25) / (55 - 25) * 60.0
        else:
            score = max(0.0, rms_contrast / 25.0 * 40.0)
        
        logger.debug(f"Contraste: RMS={rms_contrast:.2f}, Score={score:.1f}%")
        
        return max(0.0, min(100.0, score))
    
    def _check_orientation(self, img: np.ndarray) -> float:
        """
        Détecte rotation document
        
        Méthode:
        1. Détection contours (Canny)
        2. Détection lignes (Hough Transform)
        3. Calcul angle moyen
        4. Score = 100% si angle ≈ 0° (horizontal)
        
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        
        lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=200)
        
        if lines is None or len(lines) < 5:
            # Pas assez de lignes → Assumer OK
            logger.debug("Orientation: Pas assez de lignes détectées, assume OK")
            return 100.0
        
        # Calculer angle moyen
        angles = []
        for line in lines[:20]:  # Max 20 lignes
            rho, theta = line[0]
            angle_deg = np.degrees(theta) - 90
            angles.append(angle_deg)
        
        mean_angle = np.mean(angles)
        abs_angle = abs(mean_angle)
        
        if abs_angle <= 3:
            score = 100.0
        elif abs_angle <= 12:
            score = 100.0 - (abs_angle - 3) / (12 - 3) * 70.0
        else:
            score = max(0.0, 30.0 - (abs_angle - 12) * 5.0) 
        
        logger.debug(f"Orientation: Angle moyen={mean_angle:.2f}°, Score={score:.1f}%")
        
        return score
    
    def _generate_suggestions(
        self,
        sharpness: float,
        contrast: float,
        resolution: float,
        orientation: float
    ) -> List[str]:
        """Génère conseils amélioration selon scores"""
        suggestions = []
        
        if sharpness < self.min_sharpness:
            suggestions.append(
                "📸 Image floue détectée. Recommandations: "
                "Utilisez un scanner, stabilisez l'appareil photo, "
                "activez la mise au point automatique."
            )
        
        if contrast < self.min_contrast:
            suggestions.append(
                "🌓 Contraste insuffisant. Recommandations: "
                "Améliorez l'éclairage, évitez les contre-jours, "
                "utilisez le flash en intérieur."
            )
        
        if resolution < 75:
            suggestions.append(
                "🔍 Résolution trop faible. Recommandations: "
                "Scanner à 300 DPI minimum, "
                "ou photographier de plus près."
            )
        
        if orientation < 90:
            suggestions.append(
                "🔄 Document mal orienté. Recommandations: "
                "Redressez le document avant photo/scan."
            )
        
        return suggestions