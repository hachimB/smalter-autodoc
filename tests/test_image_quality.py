# tests/unit/test_image_quality.py
import pytest
from pathlib import Path
from src.smalter_autodoc.core.image_quality_checker import ImageQualityChecker

@pytest.fixture
def checker():
    return ImageQualityChecker()

@pytest.fixture
def fixtures_dir():
    return Path(__file__).parent.parent / "tests/test_files/"

def test_high_quality_image(checker, fixtures_dir):
    """Test image nette, bon contraste, 300 DPI"""
    image_path = fixtures_dir / "welcome_img.png"
    
    score = checker.check_quality(image_path)
    
    assert score.passed == True
    assert score.overall >= 70.0
    assert score.sharpness >= 45.0
    assert score.contrast >= 35.0

def test_blurry_image(checker, fixtures_dir):
    """Test image floue → rejet"""
    image_path = fixtures_dir / "image_floue.jpg"
    
    score = checker.check_quality(image_path)
    
    assert score.passed == False
    assert score.sharpness < 45.0
    assert len(score.suggestions) > 0
    assert any("floue" in s.lower() for s in score.suggestions)

def test_low_resolution_image(checker, fixtures_dir):
    """Test image basse résolution → rejet"""
    image_path = fixtures_dir / "image_floue.jpg"
    
    score = checker.check_quality(image_path)
    
    assert score.passed == False
    assert score.resolution < 70.0