"""Streamlit web application for MathPix Clone - Matching Desktop UI Flow."""
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

# Load secrets
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
from streamlit_cropper import st_cropper

from core.config import settings

# Force load API key from secrets for Streamlit Cloud (Failsafe)
try:
    if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
        settings.openai_api_key = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass

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

# CSS
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp { background-color: #1a1a2e; }
    [data-testid="stSidebar"] { background-color: #16213e; }
    
    .formula-card {
        background: #1e3a5f;
        border: 1px solid #3d5a80;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
    }
    .formula-card img {
        max-height: 80px;
        width: 100%;
        object-fit: contain;
        background: white;
        border-radius: 4px;
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
if "extraction_complete" not in st.session_state:
    st.session_state.extraction_complete = False
if "manual_snip_result" not in st.session_state:
    st.session_state.manual_snip_result = None

services = get_services()
if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
    try:
        services["latex_ocr"].set_api_key(st.secrets["OPENAI_API_KEY"])
        # logger.info("Explicitly set OpenAI API key on latex_ocr service")
    except Exception:
        pass

# ============================================================================
# LEFT SIDEBAR - Upload & Formula List (like desktop)
# ============================================================================
with st.sidebar:
    # DEBUG INFO
    with st.expander("🔧 Debug / Diagnostics"):
        import os
        from core.config import settings
        
        has_env_key = bool(os.getenv("OPENAI_API_KEY"))
        has_conf_key = bool(settings.openai_api_key)
        
        st.write(f"**OpenAI Key (Env):** {'✅ Set' if has_env_key else '❌ Missing'}")
        st.write(f"**OpenAI Key (Conf):** {'✅ Set' if has_conf_key else '❌ Missing'}")
        
        if st.toggle("Show System Logs"):
             try:
                 with open("mathpix_debug.log", "r") as f:
                     st.code(f.read()[-2000:], language="text")
             except FileNotFoundError:
                 st.info("Log file not found")

        if st.button("🔌 Test OpenAI Connection"):
            try:
                import openai
                client = openai.OpenAI(api_key=settings.openai_api_key or os.getenv("OPENAI_API_KEY"))
                st.info("Attempting to connect...")
                models = client.models.list()
                st.success(f"✅ Connection Successful! Found {len(list(models))} models.")
            except ImportError:
                st.error("❌ 'openai' library not installed.")
            except Exception as e:
                st.error(f"❌ Connection Failed: {e}")

        if st.button("Reload Config"):
            st.rerun()

    st.markdown("### 📁 Upload")
    
    # Single unified uploader for PDF or Image
    uploaded_file = st.file_uploader(
        "Drag and drop file here",
        type=["pdf", "png", "jpg", "jpeg"],
        help="Upload PDF document or equation image"
    )
    
    if uploaded_file:
        file_size = len(uploaded_file.getvalue()) / (1024 * 1024)
        file_type = uploaded_file.type
        
        st.success(f"📄 {uploaded_file.name} ({file_size:.2f}MB)")
        
        # Track file changes
        file_id = f"{uploaded_file.name}_{uploaded_file.size}"
        if "current_file_id" not in st.session_state or st.session_state.current_file_id != file_id:
            st.session_state.current_file_id = file_id
            st.session_state.page_images = []
            st.session_state.formulas = []
            st.session_state.selected_formula = None
            st.session_state.extraction_complete = False
            st.session_state.current_page = 0
            st.session_state.manual_snip_result = None
            
            # Load document immediately (like desktop)
            with st.spinner("Loading document..."):
                try:
                    if file_type == "application/pdf":
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(uploaded_file.getvalue())
                            tmp_path = Path(tmp.name)
                        
                        pages = services["pdf_reader"].read_pdf(tmp_path)
                        images = services["pdf_renderer"].render_pages(pages)
                        st.session_state.page_images = [str(img) for img in images]
                        st.info(f"📄 Loaded {len(images)} page(s)")
                    else:
                        # Direct image upload
                        image = Image.open(uploaded_file)
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                            image.save(tmp.name, "PNG")
                        st.session_state.page_images = [tmp.name]
                        st.info("🖼️ Image loaded")
                except Exception as e:
                    st.error(f"Failed to load: {e}")
    
    st.markdown("---")
    
    # Extract Formulas Button - Triggers full OCR pipeline (like desktop)
    if st.session_state.page_images and not st.session_state.extraction_complete:
        if st.button("🔍 Extract Formulas", type="primary", width="stretch"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            all_formulas = []
            total_pages = len(st.session_state.page_images)
            
            for page_idx, image_path in enumerate(st.session_state.page_images):
                page_num = page_idx + 1
                status_text.text(f"🔍 Detecting formulas on page {page_num}/{total_pages}...")
                progress_bar.progress((page_idx) / total_pages)
                
                try:
                    # 1. Detect formula regions (like desktop)
                    detected = services["detector"].detect_formulas(image_path)
                    
                    # 2. Filter reasonable-sized formulas
                    filtered = [f for f in detected if f.get("w", 0) * f.get("h", 0) > 200 
                               and f.get("w", 0) > 30 and f.get("h", 0) > 10]
                    
                    # 3. For each formula: Crop → OCR → MathML (like desktop run_detection)
                    for idx, formula in enumerate(filtered):
                        status_text.text(f"📝 Page {page_num}: Extracting formula {idx+1}/{len(filtered)}...")
                        
                        try:
                            # Crop the formula region
                            crop_path = crop_image(Path(image_path), formula)
                            
                            # OCR to LaTeX
                            latex = services["latex_ocr"].image_to_latex(crop_path)
                            
                            # Convert to MathML
                            mathml = services["latex_mathml"].convert(latex) if latex else ""
                            
                            # Check validity
                            is_valid = bool(latex and mathml and "<math" in mathml)
                            
                            all_formulas.append({
                                "page": page_num,
                                "idx": idx + 1,
                                "bbox": formula,
                                "image_path": str(image_path),
                                "crop_path": str(crop_path),
                                "latex": latex or "",
                                "mathml": mathml or "",
                                "is_valid": is_valid
                            })
                        except Exception as e:
                            logger.warning(f"Formula extraction failed: {e}")
                            # Still add with error
                            all_formulas.append({
                                "page": page_num,
                                "idx": idx + 1,
                                "bbox": formula,
                                "image_path": str(image_path),
                                "crop_path": "",
                                "latex": f"Error: {e}",
                                "mathml": "",
                                "is_valid": False
                            })
                            
                except Exception as e:
                    logger.error(f"Detection failed on page {page_num}: {e}")
            
            progress_bar.progress(1.0)
            status_text.text(f"✅ Extracted {len(all_formulas)} formulas!")
            
            st.session_state.formulas = all_formulas
            st.session_state.extraction_complete = True
            
            if all_formulas:
                st.session_state.selected_formula = 0
            
            st.rerun()
    
    # Formula Count & List (like desktop sidebar)
    if st.session_state.formulas:
        st.markdown("---")
        st.markdown(f"""
        <div class="formula-count">
            <div style="color: #8892b0;">📊 Formulas Found</div>
            <div class="number">{len(st.session_state.formulas)}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 📋 Formula List")
        
        # List each formula with preview image (like desktop FormulaListPanel)
        for i, formula in enumerate(st.session_state.formulas):
            is_selected = st.session_state.selected_formula == i
            page_num = formula.get("page", 1)
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                # Show cropped image preview
                if formula.get("crop_path") and Path(formula["crop_path"]).exists():
                    try:
                        st.image(formula["crop_path"], width=60)
                    except Exception:
                        st.markdown("📐")
                else:
                    st.markdown("📐")
            
            with col2:
                # Valid indicator
                status = "✅" if formula.get("is_valid") else "⚠️"
                btn_type = "primary" if is_selected else "secondary"
                
                if st.button(f"{status} F{i+1} (P{page_num})", key=f"f_{i}", width="stretch", type=btn_type):
                    st.session_state.selected_formula = i
                    st.rerun()

# ============================================================================
# MAIN AREA - Preview & MathML Output
# ============================================================================
col_preview, col_right = st.columns([3, 2])

# CENTER: Document/Page Preview
with col_preview:
    st.markdown("### 📄 Document Preview")
    
    # Selection Mode Toggle
    crop_mode = st.toggle("✂️ Enable Selection (Drag to Crop)", value=False, help="Enable this to manually select an equation from the page")
    
    if st.session_state.page_images:
        # Multi-page navigation - MORE PROMINENT
        if len(st.session_state.page_images) > 1:
            col_p1, col_p2 = st.columns([1, 1])
            with col_p1:
                page_num = st.number_input(
                    "Page",
                    min_value=1,
                    max_value=len(st.session_state.page_images),
                    value=st.session_state.current_page + 1,
                    step=1,
                    key="page_input"
                )
                st.session_state.current_page = page_num - 1
            with col_p2:
                st.markdown(f"<p style='padding-top: 32px;'>of {len(st.session_state.page_images)} pages</p>", unsafe_allow_html=True)
        
        # Show current page / Cropper
        if st.session_state.current_page < len(st.session_state.page_images):
            img_path = st.session_state.page_images[st.session_state.current_page]
            img = Image.open(img_path)
            
            if crop_mode:
                st.info("💡 Drag the box over an equation to select it")
                cropped_img = st_cropper(img, realtime_update=True, box_color='#00d4ff', aspect_ratio=None)
                
                # Auto-process the crop
                if cropped_img:
                    # Update manual snip result with this crop
                    with st.spinner("Extracting from selection..."):
                        try:
                            # Convert PIL image to bytes for processing
                            buf = io.BytesIO()
                            cropped_img.save(buf, format="PNG")
                            buf.seek(0)
                            
                            # Save to temp file for OCR service
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                                tmp.write(buf.getvalue())
                                tmp_path = Path(tmp.name)
                            
                            latex = services["latex_ocr"].image_to_latex(tmp_path)
                            mathml = services["latex_mathml"].convert(latex) if latex else ""
                            
                            st.session_state.manual_snip_result = {
                                "latex": latex or "",
                                "mathml": mathml or "",
                                "is_valid": bool(latex and mathml and "<math" in mathml),
                                "is_crop": True,
                                "image": cropped_img # Store the PIL image
                            }
                        except Exception as e:
                            st.error(f"Crop OCR failed: {e}")
            else:
                st.image(img, width="stretch")
        else:
            st.session_state.current_page = 0
            st.rerun()
        
        # Show formula count for this page
        page_formulas = [f for f in st.session_state.formulas if f.get("page") == st.session_state.current_page + 1]
        if page_formulas:
            st.success(f"📍 {len(page_formulas)} formula(s) detected on this page")
        else:
            st.info("No formulas detected on this page yet. Click 'Extract Formulas' in the sidebar.")
    else:
        st.markdown("""
        <div style="
            border: 2px dashed #3d5a80;
            border-radius: 12px;
            padding: 60px 40px;
            text-align: center;
            color: #8892b0;
        ">
            <h2>📄 Document Preview</h2>
            <p>Upload a PDF or image from the sidebar</p>
        </div>
        """, unsafe_allow_html=True)

# RIGHT: Formula Details / MathML Output (like desktop PreviewPanel)
with col_right:
    st.markdown("### 📐 MathML Output")
    
    # -------------------------------------------------------------------------
    # OPTION A: MANUAL SNIP UPLOAD (Simulates "Drag to Select")
    # -------------------------------------------------------------------------
    st.markdown("#### ✂️ Manual Snip Upload")
    manual_snip = st.file_uploader(
        "Drop a manual snip (screenshot) here for instant MathML:",
        type=["png", "jpg", "jpeg"],
        key="manual_snip_uploader"
    )
    
    if manual_snip:
        # Auto-process manual snip
        snip_id = f"{manual_snip.name}_{manual_snip.size}"
        if "last_snip_id" not in st.session_state or st.session_state.last_snip_id != snip_id:
            st.session_state.last_snip_id = snip_id
            with st.spinner("Processing manual snip..."):
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                        tmp.write(manual_snip.getvalue())
                        tmp_path = Path(tmp.name)
                    
                    latex = services["latex_ocr"].image_to_latex(tmp_path)
                    mathml = services["latex_mathml"].convert(latex) if latex else ""
                    st.session_state.manual_snip_result = {
                        "latex": latex or "",
                        "mathml": mathml or "",
                        "is_valid": bool(latex and mathml and "<math" in mathml),
                        "image": Image.open(tmp_path) # Store the image
                    }
                except Exception as e:
                    st.error(f"Manual snip failed: {e}")
    
    if st.session_state.manual_snip_result:
        st.markdown("---")
        st.markdown("#### 🔍 Manual Snip Result")
        res = st.session_state.manual_snip_result
        
        # 1. Image Overview
        if "image" in res:
            st.markdown("**🖼️ Image Overview:**")
            st.image(res["image"], width="stretch")
        
        # 2. Equation Rendering
        if res.get("latex"):
            st.markdown("**✨ Equation Rendering:**")
            st.latex(res["latex"])
            
        if res.get("mathml"):
            st.markdown("**📄 MathML Code:**")
            st.code(res["mathml"], language="xml")
            st.download_button("📥 Download Snip MathML", res["mathml"], "snip_formula.mml", "application/xml")
            
            # Enhance with AI Button (Manual Snip)
            st.markdown("---")
            if st.button("✨ Enhance with Cloud AI (Better Accuracy)", key="enhance_snip", help="Use GPT-4 Vision to fix broken equations"):
                if not services["latex_ocr"].has_vision_fallback_configured():
                   st.warning("⚠️ OpenAI API Key needed for enhancement")
                   api_key = st.text_input("Enter OpenAI API Key:", type="password", key="snip_api_key")
                   if api_key:
                        services["latex_ocr"].set_api_key(api_key)
                        st.rerun()
                else:
                    if "image" in res:
                        with st.spinner("✨ Enhancing with GPT-4 Vision..."):
                            try:
                                # Save image to temp for processing
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                                    res["image"].save(tmp, format="PNG")
                                    tmp_path = Path(tmp.name)
                                
                                # Process with forced Vision
                                latex = services["latex_ocr"].image_to_latex(tmp_path, handwriting_mode=True) # handwriting_mode forces Vision
                                mathml = services["latex_mathml"].convert(latex) if latex else ""
                                
                                st.session_state.manual_snip_result["latex"] = latex
                                st.session_state.manual_snip_result["mathml"] = mathml
                                st.session_state.manual_snip_result["is_valid"] = True
                                st.rerun()
                            except Exception as e:
                                st.error(f"Enhancement failed: {e}")
        st.markdown("---")

    # -------------------------------------------------------------------------
    # OPTION B: DETECTED FORMULAS (From Sidebar Extract)
    # -------------------------------------------------------------------------
    if st.session_state.selected_formula is not None and st.session_state.formulas:
        formula = st.session_state.formulas[st.session_state.selected_formula]
        
        st.markdown(f"#### 📍 Formula {st.session_state.selected_formula + 1} (Page {formula.get('page')})")
        
        # 1. Image Overview (Cropped Region)
        if formula.get("crop_path") and Path(formula["crop_path"]).exists():
            st.markdown("**🖼️ Image Overview:**")
            st.image(formula["crop_path"], width="stretch")
        
        # 2. Equation Rendering
        latex = formula.get("latex", "")
        if latex:
            st.markdown("**✨ Equation Rendering:**")
            st.latex(latex)
        else:
            st.warning("No LaTeX extracted")
        
        # 3. MathML
        st.markdown("**📄 MathML Code:**")
        mathml = formula.get("mathml", "")
        if mathml:
            st.code(mathml, language="xml")
            if formula.get("is_valid"):
                st.success("✅ Valid MathML")
            else:
                st.warning("⚠️ MathML may have issues")
        else:
            st.error("❌ No MathML generated")
        
        # Enhance with AI Button (Formulas)
        st.markdown("---")
        if st.button("✨ Enhance with Cloud AI (Better Accuracy)", key=f"enhance_f{st.session_state.selected_formula}", help="Use GPT-4 Vision to fix broken equations"):
            if not services["latex_ocr"].has_vision_fallback_configured():
                st.warning("⚠️ OpenAI API Key needed for enhancement")
                api_key = st.text_input("Enter OpenAI API Key:", type="password", key="formula_api_key")
                if api_key:
                    services["latex_ocr"].set_api_key(api_key)
                    st.rerun()
            else:
                crop_path = formula.get("crop_path")
                if crop_path and Path(crop_path).exists():
                    with st.spinner("✨ Enhancing with GPT-4 Vision..."):
                        try:
                            # Process with forced Vision (handwriting_mode=True forces Vision)
                            latex = services["latex_ocr"].image_to_latex(crop_path, handwriting_mode=True)
                            mathml = services["latex_mathml"].convert(latex) if latex else ""
                            
                            # Update formula in state
                            st.session_state.formulas[st.session_state.selected_formula]["latex"] = latex
                            st.session_state.formulas[st.session_state.selected_formula]["mathml"] = mathml
                            st.session_state.formulas[st.session_state.selected_formula]["is_valid"] = True
                            st.rerun()
                        except Exception as e:
                            st.error(f"Enhancement failed: {e}")
                else:
                    st.error("No image available for enhancement")
        st.markdown("---")
        
        # Download buttons
        col1, col2 = st.columns(2)
        with col1:
            if latex:
                st.download_button("📥 LaTeX", latex, f"f{st.session_state.selected_formula+1}.tex", "text/plain")
        with col2:
            if mathml:
                st.download_button("📥 MathML", mathml, f"f{st.session_state.selected_formula+1}.mml", "application/xml")
    
    elif not st.session_state.extraction_complete:
        st.info("👆 Click 'Extract Formulas' in the sidebar to auto-detect every equation on the PDF, OR upload a manual snip above.")
