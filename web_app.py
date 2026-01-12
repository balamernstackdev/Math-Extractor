"""Streamlit web application for MathPix Clone - Free deployment option."""
from __future__ import annotations

import os
import tempfile

# -------------------------------------------------------------------------
# CRITICAL: Set writable cache directories BEFORE importing ML libraries
# Streamlit Cloud's venv is read-only, so pix2tex can't download weights there
# -------------------------------------------------------------------------
_cache_dir = os.path.join(tempfile.gettempdir(), "mathpix_cache")
os.makedirs(_cache_dir, exist_ok=True)

# Set all ML-related cache paths to writable location
os.environ["HF_HOME"] = os.path.join(_cache_dir, "huggingface")
os.environ["TORCH_HOME"] = os.path.join(_cache_dir, "torch")
os.environ["TIMM_CACHE"] = os.path.join(_cache_dir, "timm")
os.environ["XDG_CACHE_HOME"] = _cache_dir  # General fallback

# pix2tex specific - force checkpoint download to writable location
os.environ["PIX2TEX_CACHE"] = os.path.join(_cache_dir, "pix2tex")

# Suppress warnings
os.environ["NO_ALBUMENTATIONS_UPDATE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import io
from pathlib import Path
from typing import List

import streamlit as st
from PIL import Image

from core.config import settings
from core.logger import init_logging, logger
from services.ocr.formula_detector import FormulaDetector
from services.ocr.image_to_latex import ImageToLatex
from services.ocr.latex_to_mathml import LatexToMathML
from services.pdf_loader.pdf_reader import PDFReader
from services.pdf_loader.pdf_renderer import PDFRenderer
from utils.file_utils import ensure_directories
from utils.image_utils import crop_image

# Initialize logging
init_logging()
ensure_directories()

# Initialize services (cached for performance)
@st.cache_resource
def get_services():
    """Initialize and cache services."""
    return {
        "pdf_reader": PDFReader(),
        "pdf_renderer": PDFRenderer(),
        "detector": FormulaDetector(),
        "latex_ocr": ImageToLatex(),
        "latex_mathml": LatexToMathML(),
    }

# Page config
st.set_page_config(
    page_title="MathPix Clone - Web",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title
st.title("📐 MathPix Clone - Web Edition")
st.markdown("Upload PDFs or images to extract mathematical formulas and convert them to LaTeX/MathML")

# Initialize session state
if "uploaded_pdf" not in st.session_state:
    st.session_state.uploaded_pdf = None
if "page_images" not in st.session_state:
    st.session_state.page_images = []
if "extracted_formulas" not in st.session_state:
    st.session_state.extracted_formulas = {}

# Sidebar
with st.sidebar:
    st.header("📁 Upload")
    uploaded_file = st.file_uploader(
        "Upload PDF or Image",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Upload a PDF document or image containing mathematical formulas"
    )
    
    if uploaded_file:
        if uploaded_file.type == "application/pdf":
            st.session_state.uploaded_pdf = uploaded_file
        else:
            # Handle image upload
            st.session_state.uploaded_pdf = uploaded_file
    
    st.markdown("---")
    st.markdown("### 🚀 Deploy Free")
    st.markdown("""
    **Streamlit Cloud** (Free):
    1. Push to GitHub
    2. Connect to [streamlit.io](https://streamlit.io)
    3. Deploy in 2 clicks!
    
    **Other Free Options:**
    - Railway.app
    - Render.com
    - Fly.io
    """)

# Main content
services = get_services()

if st.session_state.uploaded_pdf:
    file_type = st.session_state.uploaded_pdf.type
    
    if file_type == "application/pdf":
        # PDF processing
        st.header("📄 PDF Processing")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(st.session_state.uploaded_pdf.read())
            tmp_path = Path(tmp_file.name)
        
        try:
            with st.spinner("Loading PDF..."):
                pages = services["pdf_reader"].read_pdf(tmp_path)
            
            with st.spinner("Rendering pages..."):
                images = services["pdf_renderer"].render_pages(pages)
                st.session_state.page_images = images
            
            st.success(f"✅ Loaded {len(images)} page(s)")
            
            # Display pages
            tab1, tab2 = st.tabs(["📄 Pages", "🔍 Formulas"])
            
            with tab1:
                for idx, image_path in enumerate(images, 1):
                    st.subheader(f"Page {idx}")
                    st.image(str(image_path), use_container_width=True)
            
            with tab2:
                if st.button("🔍 Detect Formulas", type="primary"):
                    with st.spinner("Detecting formulas..."):
                        formulas_by_page = {}
                        for page_num, image_path in enumerate(images, 1):
                            try:
                                formulas = services["detector"].detect_formulas(image_path)
                                # Filter reasonable-sized formulas
                                filtered = [
                                    f for f in formulas 
                                    if f.get("w", 0) * f.get("h", 0) > 200 
                                    and f.get("w", 0) > 30 
                                    and f.get("h", 0) > 10
                                ]
                                formulas_by_page[page_num] = filtered
                            except Exception as e:
                                logger.error(f"Detection failed for page {page_num}: {e}")
                                formulas_by_page[page_num] = []
                        
                        st.session_state.extracted_formulas = formulas_by_page
                    
                    total = sum(len(f) for f in formulas_by_page.values())
                    st.success(f"✅ Detected {total} formula(s)")
                
                # Display extracted formulas
                if st.session_state.extracted_formulas:
                    for page_num, formulas in st.session_state.extracted_formulas.items():
                        if formulas:
                            st.subheader(f"Page {page_num} - {len(formulas)} formula(s)")
                            
                            for idx, formula in enumerate(formulas, 1):
                                with st.expander(f"Formula {idx}"):
                                    col1, col2 = st.columns(2)
                                    
                                    with col1:
                                        # Crop and show formula
                                        try:
                                            crop_path = crop_image(
                                                Path(images[page_num - 1]), 
                                                formula
                                            )
                                            st.image(str(crop_path), caption="Formula Image")
                                            
                                            # OCR
                                            with st.spinner("Extracting LaTeX..."):
                                                latex = services["latex_ocr"].image_to_latex(crop_path)
                                            
                                            st.code(latex, language="latex")
                                            
                                            # Convert to MathML
                                            if latex and latex.strip():
                                                mathml = services["latex_mathml"].convert(latex)
                                                st.code(mathml, language="xml")
                                                
                                                # Download buttons
                                                col_d1, col_d2 = st.columns(2)
                                                with col_d1:
                                                    st.download_button(
                                                        "📥 Download LaTeX",
                                                        latex,
                                                        file_name=f"formula_{page_num}_{idx}.tex",
                                                        mime="text/plain"
                                                    )
                                                with col_d2:
                                                    st.download_button(
                                                        "📥 Download MathML",
                                                        mathml,
                                                        file_name=f"formula_{page_num}_{idx}.xml",
                                                        mime="application/xml"
                                                    )
                                        except Exception as e:
                                            st.error(f"Error processing formula: {e}")
                                    
                                    with col2:
                                        st.json(formula)
        
        except Exception as e:
            st.error(f"Error processing PDF: {e}")
            logger.exception("PDF processing failed")
        finally:
            # Cleanup
            if tmp_path.exists():
                tmp_path.unlink()
    
    else:
        # Image processing
        st.header("🖼️ Image Processing")
        
        image = Image.open(st.session_state.uploaded_pdf)
        st.image(image, caption="Uploaded Image", use_container_width=True)
        
        if st.button("🔍 Extract Formulas", type="primary"):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                image.save(tmp_file.name, "PNG")
                tmp_path = Path(tmp_file.name)
            
            try:
                with st.spinner("Detecting formulas..."):
                    formulas = services["detector"].detect_formulas(tmp_path)
                    filtered = [
                        f for f in formulas 
                        if f.get("w", 0) * f.get("h", 0) > 200 
                        and f.get("w", 0) > 30 
                        and f.get("h", 0) > 10
                    ]
                
                if filtered:
                    st.success(f"✅ Detected {len(filtered)} formula(s)")
                    
                    for idx, formula in enumerate(filtered, 1):
                        with st.expander(f"Formula {idx}"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                try:
                                    crop_path = crop_image(tmp_path, formula)
                                    st.image(str(crop_path), caption="Formula Image")
                                    
                                    with st.spinner("Extracting LaTeX..."):
                                        latex = services["latex_ocr"].image_to_latex(crop_path)
                                    
                                    st.code(latex, language="latex")
                                    
                                    if latex and latex.strip():
                                        mathml = services["latex_mathml"].convert(latex)
                                        st.code(mathml, language="xml")
                                        
                                        col_d1, col_d2 = st.columns(2)
                                        with col_d1:
                                            st.download_button(
                                                "📥 Download LaTeX",
                                                latex,
                                                file_name=f"formula_{idx}.tex",
                                                mime="text/plain"
                                            )
                                        with col_d2:
                                            st.download_button(
                                                "📥 Download MathML",
                                                mathml,
                                                file_name=f"formula_{idx}.xml",
                                                mime="application/xml"
                                            )
                                except Exception as e:
                                    st.error(f"Error: {e}")
                            
                            with col2:
                                st.json(formula)
                else:
                    st.warning("No formulas detected. Try selecting a region manually.")
                    
                    # Manual region selection
                    st.info("💡 Tip: Use the desktop app for manual region selection")
            
            except Exception as e:
                st.error(f"Error processing image: {e}")
                logger.exception("Image processing failed")
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()

else:
    # Welcome screen
    st.markdown("""
    ### Welcome to MathPix Clone Web Edition! 🌐
    
    **Features:**
    - 📄 Upload PDFs and extract formulas
    - 🖼️ Upload images with mathematical content
    - 🔍 Automatic formula detection
    - 📝 LaTeX and MathML export
    - 💾 Download extracted formulas
    
    **How to use:**
    1. Upload a PDF or image using the sidebar
    2. Wait for processing
    3. Click "Detect Formulas" to find mathematical expressions
    4. View and download LaTeX/MathML
    
    **Free Deployment:**
    - Deploy to Streamlit Cloud (free)
    - Access from any device with a browser
    - No installation required
    """)
    
    st.markdown("---")
    st.markdown("### 📚 Desktop App")
    st.info("For advanced features like manual region selection, use the desktop app: `python app.py`")

