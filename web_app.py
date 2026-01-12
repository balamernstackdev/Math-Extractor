"""Streamlit web application for MathPix Clone - Matching Desktop UI."""
from __future__ import annotations

import os
import tempfile
import base64

# -------------------------------------------------------------------------
# CRITICAL: Set writable cache directories BEFORE importing ML libraries
# -------------------------------------------------------------------------
_cache_dir = os.path.join(tempfile.gettempdir(), "mathpix_cache")
os.makedirs(_cache_dir, exist_ok=True)

os.environ["HF_HOME"] = os.path.join(_cache_dir, "huggingface")
os.environ["TORCH_HOME"] = os.path.join(_cache_dir, "torch")
os.environ["TIMM_CACHE"] = os.path.join(_cache_dir, "timm")
os.environ["XDG_CACHE_HOME"] = _cache_dir
os.environ["PIX2TEX_CACHE"] = os.path.join(_cache_dir, "pix2tex")
os.environ["NO_ALBUMENTATIONS_UPDATE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# -------------------------------------------------------------------------
# LOAD SECRETS: Streamlit Cloud secrets OR .env file
# -------------------------------------------------------------------------
try:
    import streamlit as st
    if hasattr(st, 'secrets') and 'OPENAI_API_KEY' in st.secrets:
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import io
from pathlib import Path
from typing import List, Dict, Any, Optional

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

# Initialize
init_logging()
ensure_directories()

# Cached services
@st.cache_resource
def get_services():
    return {
        "pdf_reader": PDFReader(),
        "pdf_renderer": PDFRenderer(),
        "detector": FormulaDetector(),
        "latex_ocr": ImageToLatex(),
        "latex_mathml": LatexToMathML(),
    }

# Page config
st.set_page_config(
    page_title="Math Extractor",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .stApp { background-color: #1a1a2e; }
    
    [data-testid="stSidebar"] {
        background-color: #16213e;
        border-right: 1px solid #2d3748;
    }
    
    .formula-preview {
        background: #1e3a5f;
        border: 1px solid #3d5a80;
        border-radius: 8px;
        padding: 8px;
        margin: 4px 0;
        cursor: pointer;
    }
    .formula-preview:hover {
        border-color: #00d4ff;
    }
    .formula-preview img {
        max-height: 60px;
        width: 100%;
        object-fit: contain;
    }
    
    .formula-count {
        background: #16213e;
        border-left: 4px solid #00d4ff;
        padding: 16px;
        margin: 16px 0;
    }
    .formula-count .number {
        font-size: 2rem;
        font-weight: bold;
        color: #00d4ff;
    }
    
    .drop-zone {
        border: 3px dashed #3d5a80;
        border-radius: 12px;
        padding: 40px;
        text-align: center;
        color: #8892b0;
        background: #16213e;
        transition: all 0.3s ease;
    }
    .drop-zone:hover {
        border-color: #00d4ff;
        background: #1e3a5f;
    }
    
    .mathml-box {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 16px;
        font-family: 'Consolas', monospace;
        font-size: 0.85rem;
        overflow-x: auto;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "page_images" not in st.session_state:
    st.session_state.page_images = []
if "formulas" not in st.session_state:
    st.session_state.formulas = []
if "selected_formula" not in st.session_state:
    st.session_state.selected_formula = None
if "current_page" not in st.session_state:
    st.session_state.current_page = 0
if "formula_results" not in st.session_state:
    st.session_state.formula_results = {}
if "cropped_images" not in st.session_state:
    st.session_state.cropped_images = {}
if "direct_image" not in st.session_state:
    st.session_state.direct_image = None
if "direct_result" not in st.session_state:
    st.session_state.direct_result = None

services = get_services()

# ============================================================================
# LEFT SIDEBAR
# ============================================================================
with st.sidebar:
    st.markdown("### 📁 Upload")
    
    # File uploader for PDF
    uploaded_file = st.file_uploader(
        "Drag and drop file here",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Upload PDF or image",
        key="main_uploader"
    )
    
    if uploaded_file:
        file_size = len(uploaded_file.getvalue()) / (1024 * 1024)
        st.success(f"📄 {uploaded_file.name} ({file_size:.1f}MB)")
        
        # Load pages immediately
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        if "current_file_id" not in st.session_state or st.session_state.current_file_id != file_id:
            st.session_state.current_file_id = file_id
            st.session_state.page_images = []
            st.session_state.formulas = []
            st.session_state.formula_results = {}
            st.session_state.cropped_images = {}
            st.session_state.selected_formula = None
            
            with st.spinner("Loading document..."):
                try:
                    if uploaded_file.type == "application/pdf":
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(uploaded_file.getvalue())
                            tmp_path = Path(tmp.name)
                        
                        pages = services["pdf_reader"].read_pdf(tmp_path)
                        images = services["pdf_renderer"].render_pages(pages)
                        st.session_state.page_images = [str(img) for img in images]
                        st.info(f"📄 Loaded {len(images)} page(s)")
                    else:
                        image = Image.open(uploaded_file)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            image.save(tmp.name, "PNG")
                        st.session_state.page_images = [tmp.name]
                except Exception as e:
                    st.error(f"Failed to load: {e}")
    
    st.markdown("---")
    
    # Extract Formulas button
    if st.session_state.page_images:
        if st.button("🔍 Extract Formulas", type="primary", use_container_width=True):
            with st.spinner("Detecting formulas on all pages..."):
                try:
                    all_formulas = []
                    for page_num, image_path in enumerate(st.session_state.page_images, 1):
                        detected = services["detector"].detect_formulas(image_path)
                        for formula in detected:
                            if formula.get("w", 0) * formula.get("h", 0) > 100:
                                formula["page"] = page_num
                                formula["image_path"] = str(image_path)
                                all_formulas.append(formula)
                    
                    st.session_state.formulas = all_formulas
                    st.session_state.formula_results = {}
                    st.session_state.cropped_images = {}
                    
                    # Pre-crop all formula images for preview
                    for idx, formula in enumerate(all_formulas):
                        try:
                            crop_path = crop_image(Path(formula["image_path"]), formula)
                            st.session_state.cropped_images[idx] = str(crop_path)
                        except Exception:
                            pass
                    
                    if all_formulas:
                        st.session_state.selected_formula = 0
                    
                    st.success(f"Found {len(all_formulas)} formulas!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    
    # Formula count and list with previews
    if st.session_state.formulas:
        st.markdown("---")
        st.markdown(f"""
        <div class="formula-count">
            <div style="color: #8892b0; font-size: 0.9rem;">📊 Formulas Found</div>
            <div class="number">{len(st.session_state.formulas)}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 📋 Formula List")
        
        # Formula list with image previews
        for idx, formula in enumerate(st.session_state.formulas):
            page_num = formula.get("page", 1)
            is_selected = st.session_state.selected_formula == idx
            
            # Show preview image if available
            col1, col2 = st.columns([1, 3])
            with col1:
                if idx in st.session_state.cropped_images:
                    try:
                        st.image(st.session_state.cropped_images[idx], width=50)
                    except Exception:
                        st.markdown("📐")
                else:
                    st.markdown("📐")
            
            with col2:
                btn_type = "primary" if is_selected else "secondary"
                if st.button(f"Formula {idx+1} (P{page_num})", key=f"f_{idx}", use_container_width=True, type=btn_type):
                    st.session_state.selected_formula = idx
                    st.rerun()

# ============================================================================
# MAIN AREA - Two columns
# ============================================================================
col_preview, col_right = st.columns([3, 2])

# CENTER: Document Preview / Image Drop Zone
with col_preview:
    # Page selector for multi-page PDFs
    if st.session_state.page_images and len(st.session_state.page_images) > 1:
        page_options = list(range(1, len(st.session_state.page_images) + 1))
        selected_page = st.selectbox(
            "Page",
            options=page_options,
            index=st.session_state.current_page,
            format_func=lambda x: f"Page {x} of {len(st.session_state.page_images)}"
        )
        st.session_state.current_page = selected_page - 1
    
    # Display current page or drop zone
    if st.session_state.page_images:
        current_img = st.session_state.page_images[st.session_state.current_page]
        st.image(current_img, use_container_width=True)
    else:
        # Drop zone for direct image upload
        st.markdown("""
        <div class="drop-zone">
            <h2>📄 Drop Image Here</h2>
            <p>Drag an equation image directly to extract MathML</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Alternative: Direct image uploader in preview area
        direct_image = st.file_uploader(
            "Or click to upload equation image",
            type=["png", "jpg", "jpeg"],
            key="direct_upload",
            label_visibility="collapsed"
        )
        
        if direct_image:
            st.session_state.direct_image = direct_image
    
    # Handle direct image upload for instant MathML
    if st.session_state.direct_image and not st.session_state.page_images:
        st.markdown("---")
        st.markdown("### 🔍 Direct Equation Extraction")
        
        img = Image.open(st.session_state.direct_image)
        st.image(img, caption="Uploaded Equation", use_container_width=True)
        
        if st.button("📐 Extract MathML", type="primary"):
            with st.spinner("Extracting LaTeX and MathML..."):
                try:
                    # Save temp image
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        img.save(tmp.name, "PNG")
                        tmp_path = Path(tmp.name)
                    
                    # OCR
                    latex = services["latex_ocr"].image_to_latex(tmp_path)
                    mathml = services["latex_mathml"].convert(latex) if latex else ""
                    
                    st.session_state.direct_result = {
                        "latex": latex or "",
                        "mathml": mathml or ""
                    }
                except Exception as e:
                    st.error(f"Extraction failed: {e}")
        
        # Show results
        if st.session_state.direct_result:
            result = st.session_state.direct_result
            
            st.markdown("**📝 LaTeX:**")
            st.code(result["latex"], language="latex")
            
            st.markdown("**📄 MathML:**")
            st.code(result["mathml"], language="xml")
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("📥 Download LaTeX", result["latex"], "equation.tex", "text/plain")
            with col2:
                st.download_button("📥 Download MathML", result["mathml"], "equation.mml", "application/xml")

# RIGHT: Formula Details
with col_right:
    st.markdown("### 📐 Formula Details")
    
    if st.session_state.selected_formula is not None and st.session_state.formulas:
        idx = st.session_state.selected_formula
        formula = st.session_state.formulas[idx]
        
        # ---- Cropped Region ----
        st.markdown("**Cropped Region:**")
        if idx in st.session_state.cropped_images:
            st.image(st.session_state.cropped_images[idx], use_container_width=True)
        
        st.markdown("---")
        
        # ---- Get/Compute LaTeX & MathML ----
        cache_key = f"formula_{idx}"
        if cache_key not in st.session_state.formula_results:
            with st.spinner("Extracting LaTeX & MathML..."):
                try:
                    crop_path = st.session_state.cropped_images.get(idx)
                    if crop_path:
                        latex = services["latex_ocr"].image_to_latex(crop_path)
                        mathml = services["latex_mathml"].convert(latex) if latex else ""
                        st.session_state.formula_results[cache_key] = {
                            "latex": latex or "",
                            "mathml": mathml or ""
                        }
                    else:
                        st.session_state.formula_results[cache_key] = {"latex": "", "mathml": ""}
                except Exception as e:
                    st.session_state.formula_results[cache_key] = {
                        "latex": f"Error: {e}",
                        "mathml": ""
                    }
        
        result = st.session_state.formula_results.get(cache_key, {})
        latex = result.get("latex", "")
        mathml = result.get("mathml", "")
        
        # ---- LaTeX ----
        st.markdown("**📝 LaTeX:**")
        st.code(latex if latex else "No LaTeX extracted", language="latex")
        
        # ---- MathML ----
        st.markdown("**📄 MathML:**")
        if mathml:
            st.code(mathml, language="xml")
        else:
            st.info("No MathML generated")
        
        # ---- Download buttons ----
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if latex:
                st.download_button(
                    "📥 LaTeX",
                    latex,
                    f"formula_{idx+1}.tex",
                    "text/plain",
                    key=f"dl_latex_{idx}"
                )
        with col2:
            if mathml:
                st.download_button(
                    "📥 MathML",
                    mathml,
                    f"formula_{idx+1}.mml",
                    "application/xml",
                    key=f"dl_mathml_{idx}"
                )
    
    elif not st.session_state.formulas and not st.session_state.direct_result:
        st.markdown("""
        <div style="
            border: 2px dashed #3d5a80;
            border-radius: 12px;
            padding: 40px 20px;
            text-align: center;
            color: #8892b0;
        ">
            <h3>📐 MathML Output</h3>
            <p>1. Upload a PDF or drag an equation image</p>
            <p>2. Click Extract Formulas</p>
            <p>3. Select a formula to see results</p>
        </div>
        """, unsafe_allow_html=True)
