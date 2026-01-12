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
from typing import List, Dict, Any

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
    page_title="Math Extractor - Web",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Dark theme styling */
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%);
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }
    .main-header h1 {
        color: #00d4ff;
        margin: 0;
    }
    
    /* Formula card styling */
    .formula-card {
        background: #1e1e2e;
        border: 1px solid #3d3d5c;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    
    /* Code block styling */
    .stCodeBlock {
        background: #0d1117 !important;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background: #0d1b2a;
    }
    
    /* Preview image container */
    .preview-container {
        border: 2px solid #3d3d5c;
        border-radius: 8px;
        padding: 0.5rem;
        background: #1a1a2e;
        margin-bottom: 0.5rem;
    }
    
    /* Formula list item */
    .formula-list-item {
        background: linear-gradient(135deg, #16213e 0%, #1a1a2e 100%);
        border-left: 3px solid #00d4ff;
        padding: 0.5rem 1rem;
        margin-bottom: 0.5rem;
        border-radius: 0 8px 8px 0;
    }
    
    /* MathML container */
    .mathml-container {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 1rem;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 0.85rem;
        overflow-x: auto;
    }
    
    /* Success/Error badges */
    .badge-success {
        background: #238636;
        color: white;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
    }
    .badge-error {
        background: #da3633;
        color: white;
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.75rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="main-header">
    <h1>📐 Math Extractor - Web Edition</h1>
    <p style="color: #8892b0; margin: 0.5rem 0 0 0;">
        Extract mathematical formulas from PDFs and images → LaTeX & MathML
    </p>
</div>
""", unsafe_allow_html=True)

# Initialize session state
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "page_images" not in st.session_state:
    st.session_state.page_images = []
if "extracted_formulas" not in st.session_state:
    st.session_state.extracted_formulas = []
if "current_page" not in st.session_state:
    st.session_state.current_page = 0
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False

# Load services
services = get_services()

# Create three-column layout: Upload | Preview | Results
col_upload, col_preview, col_results = st.columns([1, 2, 2])

# LEFT COLUMN: Upload Section
with col_upload:
    st.markdown("### 📁 Upload")
    
    uploaded_file = st.file_uploader(
        "Drop PDF or Image",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Upload a PDF document or image containing mathematical formulas",
        key="file_uploader"
    )
    
    if uploaded_file:
        st.session_state.uploaded_file = uploaded_file
        file_size = len(uploaded_file.getvalue()) / 1024
        st.success(f"✅ {uploaded_file.name}")
        st.caption(f"Size: {file_size:.1f} KB")
    
    st.markdown("---")
    
    # Processing button
    if st.session_state.uploaded_file:
        if st.button("🔍 Extract Formulas", type="primary", use_container_width=True):
            st.session_state.processing_complete = False
            st.session_state.extracted_formulas = []
            
            with st.spinner("Processing..."):
                try:
                    file_type = st.session_state.uploaded_file.type
                    
                    if file_type == "application/pdf":
                        # Save PDF temporarily
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                            tmp_file.write(st.session_state.uploaded_file.getvalue())
                            tmp_path = Path(tmp_file.name)
                        
                        # Read and render PDF
                        pages = services["pdf_reader"].read_pdf(tmp_path)
                        images = services["pdf_renderer"].render_pages(pages)
                        st.session_state.page_images = [str(img) for img in images]
                        
                        # Detect formulas on each page
                        all_formulas = []
                        for page_num, image_path in enumerate(images, 1):
                            formulas = services["detector"].detect_formulas(image_path)
                            for idx, formula in enumerate(formulas):
                                if formula.get("w", 0) * formula.get("h", 0) > 200:
                                    formula["page"] = page_num
                                    formula["image_path"] = str(image_path)
                                    all_formulas.append(formula)
                        
                        st.session_state.extracted_formulas = all_formulas
                        tmp_path.unlink()
                        
                    else:
                        # Image processing
                        image = Image.open(st.session_state.uploaded_file)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                            image.save(tmp_file.name, "PNG")
                            tmp_path = Path(tmp_file.name)
                        
                        st.session_state.page_images = [str(tmp_path)]
                        
                        # Detect formulas
                        formulas = services["detector"].detect_formulas(tmp_path)
                        all_formulas = []
                        for idx, formula in enumerate(formulas):
                            if formula.get("w", 0) * formula.get("h", 0) > 200:
                                formula["page"] = 1
                                formula["image_path"] = str(tmp_path)
                                all_formulas.append(formula)
                        
                        st.session_state.extracted_formulas = all_formulas
                    
                    st.session_state.processing_complete = True
                    
                except Exception as e:
                    st.error(f"Error: {e}")
                    logger.exception("Processing failed")
    
    # Show formula count
    if st.session_state.extracted_formulas:
        st.markdown("---")
        st.metric("📊 Formulas Found", len(st.session_state.extracted_formulas))
    
    # Formula list in sidebar
    if st.session_state.extracted_formulas:
        st.markdown("### 📋 Formula List")
        for idx, formula in enumerate(st.session_state.extracted_formulas):
            page_num = formula.get("page", 1)
            if st.button(f"Formula {idx+1} (Page {page_num})", key=f"formula_btn_{idx}", use_container_width=True):
                st.session_state.selected_formula = idx

# MIDDLE COLUMN: Preview
with col_preview:
    st.markdown("### 📄 Document Preview")
    
    if st.session_state.page_images:
        # Page navigation
        if len(st.session_state.page_images) > 1:
            page_num = st.selectbox(
                "Select Page",
                range(1, len(st.session_state.page_images) + 1),
                format_func=lambda x: f"Page {x}"
            )
            st.session_state.current_page = page_num - 1
        else:
            st.session_state.current_page = 0
        
        # Display current page
        current_image = st.session_state.page_images[st.session_state.current_page]
        st.image(current_image, use_container_width=True, caption=f"Page {st.session_state.current_page + 1}")
        
        # Show detected formula regions as overlays (info)
        page_formulas = [f for f in st.session_state.extracted_formulas 
                        if f.get("page", 1) == st.session_state.current_page + 1]
        if page_formulas:
            st.info(f"📍 {len(page_formulas)} formula(s) detected on this page")
    else:
        # Placeholder
        st.markdown("""
        <div style="
            border: 2px dashed #3d3d5c;
            border-radius: 10px;
            padding: 3rem;
            text-align: center;
            color: #8892b0;
        ">
            <h3>📄 Document Preview</h3>
            <p>Upload a PDF or image to see preview</p>
        </div>
        """, unsafe_allow_html=True)

# RIGHT COLUMN: Results (LaTeX & MathML)
with col_results:
    st.markdown("### 🧮 Extracted Equations")
    
    if st.session_state.extracted_formulas and st.session_state.processing_complete:
        # Process each formula
        for idx, formula in enumerate(st.session_state.extracted_formulas):
            with st.expander(f"📐 Formula {idx+1} (Page {formula.get('page', 1)})", expanded=(idx == 0)):
                # Create two columns for image and results
                img_col, result_col = st.columns([1, 2])
                
                with img_col:
                    try:
                        # Crop formula from image
                        crop_path = crop_image(Path(formula["image_path"]), formula)
                        st.image(str(crop_path), caption="Cropped Region", use_container_width=True)
                    except Exception as e:
                        st.error(f"Could not crop: {e}")
                
                with result_col:
                    try:
                        # Extract LaTeX
                        crop_path = crop_image(Path(formula["image_path"]), formula)
                        
                        with st.spinner("Extracting LaTeX..."):
                            latex = services["latex_ocr"].image_to_latex(crop_path)
                        
                        # LaTeX output
                        st.markdown("**📝 LaTeX:**")
                        st.code(latex if latex else "No LaTeX extracted", language="latex")
                        
                        # MathML output
                        if latex and latex.strip():
                            with st.spinner("Converting to MathML..."):
                                mathml = services["latex_mathml"].convert(latex)
                            
                            st.markdown("**📄 MathML:**")
                            st.code(mathml if mathml else "Conversion failed", language="xml")
                            
                            # Download buttons
                            dl_col1, dl_col2 = st.columns(2)
                            with dl_col1:
                                st.download_button(
                                    "📥 LaTeX",
                                    latex,
                                    file_name=f"formula_{idx+1}.tex",
                                    mime="text/plain",
                                    key=f"dl_latex_{idx}"
                                )
                            with dl_col2:
                                if mathml:
                                    st.download_button(
                                        "📥 MathML",
                                        mathml,
                                        file_name=f"formula_{idx+1}.mml",
                                        mime="application/xml",
                                        key=f"dl_mathml_{idx}"
                                    )
                        
                    except Exception as e:
                        st.error(f"Extraction failed: {e}")
                        logger.exception(f"Formula {idx+1} extraction failed")
        
        # Export all button
        st.markdown("---")
        if st.button("📦 Export All Formulas", use_container_width=True):
            # Collect all formulas
            all_latex = []
            all_mathml = []
            
            for idx, formula in enumerate(st.session_state.extracted_formulas):
                try:
                    crop_path = crop_image(Path(formula["image_path"]), formula)
                    latex = services["latex_ocr"].image_to_latex(crop_path)
                    if latex:
                        all_latex.append(f"% Formula {idx+1}\n{latex}\n")
                        mathml = services["latex_mathml"].convert(latex)
                        if mathml:
                            all_mathml.append(f"<!-- Formula {idx+1} -->\n{mathml}\n")
                except Exception:
                    pass
            
            # Download combined files
            if all_latex:
                st.download_button(
                    "📥 Download All LaTeX",
                    "\n".join(all_latex),
                    file_name="all_formulas.tex",
                    mime="text/plain"
                )
            if all_mathml:
                st.download_button(
                    "📥 Download All MathML",
                    "\n".join(all_mathml),
                    file_name="all_formulas.mml",
                    mime="application/xml"
                )
    
    elif not st.session_state.uploaded_file:
        st.markdown("""
        <div style="
            border: 2px dashed #3d3d5c;
            border-radius: 10px;
            padding: 2rem;
            text-align: center;
            color: #8892b0;
        ">
            <h3>🧮 Equations</h3>
            <p>Extracted LaTeX and MathML will appear here</p>
            <br>
            <p><strong>Steps:</strong></p>
            <ol style="text-align: left; display: inline-block;">
                <li>Upload a PDF or image</li>
                <li>Click "Extract Formulas"</li>
                <li>View and download results</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
    
    elif st.session_state.uploaded_file and not st.session_state.processing_complete:
        st.info("👆 Click 'Extract Formulas' to process the document")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #8892b0; font-size: 0.85rem;">
    <p>
        📐 <strong>Math Extractor</strong> | 
        Powered by pix2tex & latex2mathml | 
        <a href="https://github.com/balamernstackdev/Math-Extractor" target="_blank">GitHub</a>
    </p>
</div>
""", unsafe_allow_html=True)
