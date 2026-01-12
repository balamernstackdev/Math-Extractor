"""Streamlit web application for MathPix Clone - Matching Desktop UI."""
from __future__ import annotations

import os
import tempfile

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

# Page config - match desktop dark theme
st.set_page_config(
    page_title="Math Extractor",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS to match desktop UI
st.markdown("""
<style>
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Dark theme base */
    .stApp {
        background-color: #1a1a2e;
    }
    
    /* Sidebar styling - dark blue like desktop */
    [data-testid="stSidebar"] {
        background-color: #16213e;
        border-right: 1px solid #2d3748;
    }
    
    /* File card styling */
    .file-card {
        background: #1e3a5f;
        border: 1px solid #3d5a80;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .file-card .icon {
        font-size: 24px;
    }
    .file-card .name {
        color: #e0e0e0;
        font-weight: 500;
    }
    .file-card .size {
        color: #8892b0;
        font-size: 0.85rem;
    }
    
    /* Extract button - orange like desktop */
    .extract-btn {
        background: linear-gradient(135deg, #e67e22 0%, #d35400 100%);
        color: white;
        padding: 12px 24px;
        border-radius: 8px;
        border: none;
        font-weight: 600;
        width: 100%;
        cursor: pointer;
    }
    
    /* Formula count card */
    .formula-count {
        background: #16213e;
        border-left: 4px solid #00d4ff;
        padding: 16px;
        margin: 16px 0;
    }
    .formula-count .number {
        font-size: 2.5rem;
        font-weight: bold;
        color: #00d4ff;
    }
    .formula-count .label {
        color: #8892b0;
        font-size: 0.9rem;
    }
    
    /* Formula list item */
    .formula-item {
        background: #1e3a5f;
        border-radius: 6px;
        padding: 10px 16px;
        margin: 4px 0;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .formula-item:hover {
        background: #2d4a6f;
    }
    .formula-item .icon {
        color: #f39c12;
    }
    
    /* Right panel - Cropped Region */
    .cropped-region-panel {
        background: #1e1e2e;
        border: 1px solid #3d3d5c;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
    }
    .panel-title {
        color: #8892b0;
        font-size: 0.85rem;
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* MathML display area */
    .mathml-display {
        background: #0d1117;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 16px;
        font-family: 'Consolas', 'Monaco', monospace;
        font-size: 0.85rem;
        color: #c9d1d9;
        overflow-x: auto;
        white-space: pre-wrap;
        word-break: break-all;
    }
    
    /* LaTeX/MathML toggle buttons */
    .toggle-btn {
        background: #21262d;
        border: 1px solid #30363d;
        color: #c9d1d9;
        padding: 8px 20px;
        border-radius: 6px;
        cursor: pointer;
        margin-right: 8px;
    }
    .toggle-btn.active {
        background: #238636;
        border-color: #238636;
    }
    
    /* Formula accordion */
    .formula-accordion {
        background: #16213e;
        border: 1px solid #2d3748;
        border-radius: 8px;
        margin: 4px 0;
        overflow: hidden;
    }
    .formula-accordion-header {
        background: #1e3a5f;
        padding: 12px 16px;
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
    }
    .formula-accordion-header:hover {
        background: #2d4a6f;
    }
    
    /* Streamlit expander styling */
    .streamlit-expanderHeader {
        background: #1e3a5f !important;
        border-radius: 6px !important;
    }
    
    /* Image preview */
    .preview-image {
        border: 2px solid #3d5a80;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
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
if "display_mode" not in st.session_state:
    st.session_state.display_mode = "mathml"  # or "latex"

services = get_services()

# ============================================================================
# LEFT SIDEBAR
# ============================================================================
with st.sidebar:
    # Browse files button
    st.markdown("### ")
    uploaded_file = st.file_uploader(
        "Browse files",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Upload PDF or image",
        label_visibility="collapsed"
    )
    
    # File upload button style
    st.markdown("""
        <style>
            [data-testid="stFileUploader"] > div > button {
                background: #e67e22;
                color: white;
                border: none;
                padding: 8px 24px;
                border-radius: 6px;
            }
        </style>
    """, unsafe_allow_html=True)
    
    if uploaded_file:
        st.session_state.uploaded_file = uploaded_file
        
        # File card display
        file_size = len(uploaded_file.getvalue()) / (1024 * 1024)  # MB
        st.markdown(f"""
        <div class="file-card">
            <span class="icon">📄</span>
            <div>
                <div class="name">{uploaded_file.name}</div>
                <div class="size">{file_size:.1f}MB</div>
            </div>
            <span style="margin-left: auto;">✕</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Checkbox for file selection
        st.checkbox(f"✓ {uploaded_file.name}", value=True, key="file_selected")
        
        # Size display
        st.caption(f"Size: {file_size * 1024:.1f} KB")
        
        # =====================================================================
        # IMMEDIATE PDF PREVIEW: Render pages as soon as file is uploaded
        # =====================================================================
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        if "current_file_id" not in st.session_state or st.session_state.current_file_id != file_id:
            # New file uploaded - render preview
            st.session_state.current_file_id = file_id
            st.session_state.page_images = []
            st.session_state.formulas = []
            st.session_state.selected_formula = None
            st.session_state.formula_results = {}
            
            with st.spinner("Loading preview..."):
                try:
                    file_type = uploaded_file.type
                    
                    if file_type == "application/pdf":
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = Path(tmp_file.name)
                        
                        pages = services["pdf_reader"].read_pdf(tmp_path)
                        images = services["pdf_renderer"].render_pages(pages)
                        st.session_state.page_images = [str(img) for img in images]
                        st.session_state.tmp_pdf_path = str(tmp_path)
                    else:
                        # Image file
                        image = Image.open(uploaded_file)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
                            image.save(tmp_file.name, "PNG")
                            tmp_path = Path(tmp_file.name)
                        st.session_state.page_images = [str(tmp_path)]
                        
                except Exception as e:
                    st.error(f"Failed to load preview: {e}")
    
    st.markdown("---")
    
    # Extract Formulas button (orange)
    if st.session_state.uploaded_file and st.session_state.page_images:
        if st.button("🔍 Extract Formulas", type="primary", use_container_width=True):
            with st.spinner("Detecting formulas..."):
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
                    
                    # Select first formula by default
                    if st.session_state.formulas:
                        st.session_state.selected_formula = 0
                    
                    st.success(f"Found {len(all_formulas)} formulas!")
                    st.rerun()
                        
                except Exception as e:
                    st.error(f"Error: {e}")
    
    # Formula count display (like desktop)
    if st.session_state.formulas:
        st.markdown("---")
        st.markdown(f"""
        <div class="formula-count">
            <div class="icon">📊</div>
            <div class="label">Formulas Found</div>
            <div class="number">{len(st.session_state.formulas)}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Formula List header
        st.markdown("### 📋 Formula List")
        
        # Formula list - clickable items
        for idx, formula in enumerate(st.session_state.formulas):
            page_num = formula.get("page", 1)
            is_selected = st.session_state.selected_formula == idx
            
            btn_type = "primary" if is_selected else "secondary"
            if st.button(
                f"▶ Formula {idx + 1} (Page {page_num})", 
                key=f"formula_list_{idx}",
                use_container_width=True,
                type=btn_type
            ):
                st.session_state.selected_formula = idx
                st.rerun()

# ============================================================================
# MAIN CONTENT AREA - Two columns: Preview | Right Panel
# ============================================================================
col_preview, col_right = st.columns([3, 2])

# CENTER: Document Preview
with col_preview:
    if st.session_state.page_images:
        # Page navigation if multiple pages
        if len(st.session_state.page_images) > 1:
            page_num = st.selectbox(
                "Page",
                range(1, len(st.session_state.page_images) + 1),
                index=st.session_state.current_page,
                format_func=lambda x: f"Page {x}",
                key="page_selector"
            )
            st.session_state.current_page = page_num - 1
        
        # Display page image
        current_img = st.session_state.page_images[st.session_state.current_page]
        st.image(current_img, use_container_width=True)
    else:
        # Empty state
        st.markdown("""
        <div style="
            border: 2px dashed #3d5a80;
            border-radius: 12px;
            padding: 80px 40px;
            text-align: center;
            color: #8892b0;
            margin: 20px;
        ">
            <h2>📄 Document Preview</h2>
            <p>Upload a PDF or image to get started</p>
        </div>
        """, unsafe_allow_html=True)

# RIGHT PANEL: Cropped Region + MathML
with col_right:
    if st.session_state.selected_formula is not None and st.session_state.formulas:
        formula = st.session_state.formulas[st.session_state.selected_formula]
        idx = st.session_state.selected_formula
        
        # ---- Cropped Region ----
        st.markdown('<p class="panel-title">Cropped Region</p>', unsafe_allow_html=True)
        
        try:
            crop_path = crop_image(Path(formula["image_path"]), formula)
            st.image(str(crop_path), use_container_width=True)
        except Exception as e:
            st.warning(f"Could not crop image: {e}")
        
        st.markdown("---")
        
        # ---- Formula Title/Label ----
        # Try to extract label from result if available
        st.markdown("### Problem")
        
        # ---- MathML Section ----
        st.markdown('<p class="panel-title">MathML:</p>', unsafe_allow_html=True)
        
        # Get or compute LaTeX/MathML for this formula
        cache_key = f"formula_{idx}"
        if cache_key not in st.session_state.formula_results:
            with st.spinner("Extracting..."):
                try:
                    crop_path = crop_image(Path(formula["image_path"]), formula)
                    latex = services["latex_ocr"].image_to_latex(crop_path)
                    mathml = services["latex_mathml"].convert(latex) if latex else ""
                    st.session_state.formula_results[cache_key] = {
                        "latex": latex or "",
                        "mathml": mathml or ""
                    }
                except Exception as e:
                    st.session_state.formula_results[cache_key] = {
                        "latex": f"Error: {e}",
                        "mathml": ""
                    }
        
        result = st.session_state.formula_results.get(cache_key, {})
        latex = result.get("latex", "")
        mathml = result.get("mathml", "")
        
        # Display MathML code
        if mathml:
            st.code(mathml, language="xml")
        else:
            st.info("No MathML generated")
        
        # ---- LaTeX / MathML Toggle Buttons ----
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button("📝 LaTeX", use_container_width=True):
                st.session_state.display_mode = "latex"
        with btn_col2:
            if st.button("📄 MathML", use_container_width=True):
                st.session_state.display_mode = "mathml"
        
        # Show LaTeX if selected
        if st.session_state.display_mode == "latex" and latex:
            st.markdown("**LaTeX:**")
            st.code(latex, language="latex")
        
        # Download buttons
        st.markdown("---")
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            if latex:
                st.download_button(
                    "📥 Download LaTeX",
                    latex,
                    file_name=f"formula_{idx+1}.tex",
                    mime="text/plain",
                    use_container_width=True
                )
        with dl_col2:
            if mathml:
                st.download_button(
                    "📥 Download MathML", 
                    mathml,
                    file_name=f"formula_{idx+1}.mml",
                    mime="application/xml",
                    use_container_width=True
                )
        
        st.markdown("---")
        
        # ---- Other Formulas (Collapsed Accordion) ----
        st.markdown("**Other Formulas:**")
        for i, f in enumerate(st.session_state.formulas):
            if i != st.session_state.selected_formula:
                with st.expander(f"▶ Formula {i + 1} (Page {f.get('page', 1)})"):
                    cache_key_i = f"formula_{i}"
                    if cache_key_i in st.session_state.formula_results:
                        r = st.session_state.formula_results[cache_key_i]
                        if r.get("mathml"):
                            st.code(r["mathml"][:200] + "..." if len(r.get("mathml", "")) > 200 else r["mathml"], language="xml")
                    if st.button(f"Select Formula {i + 1}", key=f"select_{i}"):
                        st.session_state.selected_formula = i
                        st.rerun()
    
    elif st.session_state.formulas:
        st.info("👈 Select a formula from the list")
    else:
        st.markdown("""
        <div style="
            border: 2px dashed #3d5a80;
            border-radius: 12px;
            padding: 40px 20px;
            text-align: center;
            color: #8892b0;
        ">
            <h3>📐 Formula Details</h3>
            <p>Cropped region, LaTeX, and MathML will appear here</p>
        </div>
        """, unsafe_allow_html=True)
