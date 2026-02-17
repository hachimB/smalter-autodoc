import pytest
from src.smalter_autodoc.core.file_type_detector import FileTypeDetector, FileType

class TestFileTypeDetector:
    """Tests unitaires pour la détection de type de fichier"""
    
    @pytest.fixture
    def detector(self):
        return FileTypeDetector()
    
    def test_pdf_native_text(self, detector):
        """Test PDF créé depuis Word avec texte natif"""
        file_type, meta = detector.detect("tests/test_files/welcome_pdf.pdf")
        
        assert file_type == FileType.PDF_NATIVE_TEXT
        assert meta['has_text'] == True
        assert meta['text_ratio'] > 0.10
        assert meta['pages'] >= 1
    
    def test_pdf_scanned_image(self, detector):
        """Test PDF de scan (image convertie)"""
        file_type, meta = detector.detect("tests/test_files/welcome_scan.pdf")
        
        assert file_type == FileType.PDF_IMAGE
        assert meta['has_text'] == False
        assert meta['text_ratio'] < 0.10
    
    def test_image_jpeg(self, detector):
        """Test image PNG"""
        file_type, meta = detector.detect("tests/test_files/welcome_img.png")
        
        assert file_type == FileType.IMAGE_PURE
        assert 'width' in meta
        assert 'height' in meta
        assert meta['format'] == 'PNG'
    
    def test_unsupported_format(self, detector):
        """Test format non supporté (ex: .docx)"""
        file_type, meta = detector.detect("tests/test_files/welcome_doc.docx")
        
        assert file_type == FileType.UNSUPPORTED
        assert 'reason' in meta or 'error' in meta