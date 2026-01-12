"""Image to LaTeX OCR service."""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import re

import pytesseract
from PIL import Image, ImageOps

from core.config import settings
from core.logger import logger
from utils.image_utils import load_image
import os
import sys
import logging
import tempfile

# SETUP ROBUST FILE LOGGER FOR EXE DEBUGGING
# This bypasses all project logging to ensure we catch mistakes
try:
    # Try to write to CWD first, fallback to TEMP
    log_filename = "mathpix_debug.log"
    log_path = os.path.join(os.getcwd(), log_filename)
    
    # Check if we can write to CWD
    try:
        with open(log_path, 'a') as f:
            pass
    except PermissionError:
        log_path = os.path.join(tempfile.gettempdir(), log_filename)

    file_handler = logging.FileHandler(log_path, mode='w', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    
    # Create specific logger
    debug_logger = logging.getLogger("mathpix_exe_debug")
    debug_logger.setLevel(logging.DEBUG)
    debug_logger.addHandler(file_handler)
    debug_logger.info(f"=== MATHPIX DEBUG LOGGER STARTED (Log Path: {log_path}) ===")
except Exception:
    debug_logger = None

def log_debug(msg):
    if debug_logger:
        debug_logger.info(msg)
    # Also log to main logger just in case
    logger.debug(f"[EXE_DEBUG] {msg}")


def normalize_ocr_latex(text: str, logger) -> str:
    """
    Normalize OCR LaTeX safely.
    NEVER rewrite real LaTeX.
    NEVER attempt regex math construction.
    """

    original = text
    text = text.strip()

    # --------------------------------------------------
    # 1. Detect REAL LaTeX presence (strict)
    # --------------------------------------------------
    def is_real_latex(s: str) -> bool:
        if re.search(r"\\[a-zA-Z]{2,}", s):  # real commands only
            return True
        if any(tok in s for tok in ["{", "}", "^", "_", "\\left", "\\right"]):
            return True
        return False

    # --------------------------------------------------
    # 2. Detect BROKEN LaTeX (must be reconstructed)
    # --------------------------------------------------
    def is_broken_latex(s: str) -> bool:
        # Truncated command
        if re.search(r"\\[a-zA-Z]$", s):
            return True

        # Broken spacing commands
        if re.search(r"\\q($|[^a-zA-Z])", s):
            return True

        # Unbalanced braces
        if s.count("{") != s.count("}"):
            return True

        # Unbalanced \left / \right
        if s.count(r"\left") != s.count(r"\right"):
            return True

        return False

    has_latex = is_real_latex(text)
    broken = is_broken_latex(text)

    logger.info(
        "[OCR] LaTeX check → has_latex=%s broken=%s preview=%s",
        has_latex, broken, text[:80]
    )

    # --------------------------------------------------
    # 3. If LaTeX exists AND is broken → STOP modifying
    # --------------------------------------------------
    if has_latex and broken:
        logger.warning("[OCR] ⚠️ Broken LaTeX detected – forwarding for reconstruction only")
        return text

    # --------------------------------------------------
    # 4. If clean LaTeX → DO NOTHING
    # --------------------------------------------------
    if has_latex and not broken:
        logger.info("[OCR] ✅ Clean LaTeX detected – skipping regex substitutions")
        return text

    # --------------------------------------------------
    # 5. PLAIN TEXT ONLY → minimal safe normalization
    # --------------------------------------------------
    try:
        # Very conservative replacements only
        text = re.sub(r"\b(sum)\b", r"\\sum", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(int)\b", r"\\int", text, flags=re.IGNORECASE)

        greek_map = {
            "alpha": "\\alpha", "beta": "\\beta", "gamma": "\\gamma",
            "delta": "\\delta", "theta": "\\theta", "lambda": "\\lambda",
            "mu": "\\mu", "pi": "\\pi", "sigma": "\\sigma", "phi": "\\phi",
            "kappa": "\\kappa", "nu": "\\nu", "xi": "\\xi", "eta": "\\eta",
            "rho": "\\rho", "tau": "\\tau", "upsilon": "\\upsilon", "chi": "\\chi", "psi": "\\psi",
            "left": "\\left", "right": "\\right",
            "sum": "\\sum", "int": "\\int",
                            
        }
        for k, v in greek_map.items():
            text = re.sub(rf"\b{k}\b", v, text, flags=re.IGNORECASE)

    except Exception as exc:
        logger.warning("[OCR] Regex normalization failed: %s", exc)
        return original

    return text


class ImageToLatex:
    """Convert images of formulas to LaTeX strings."""

    def __init__(self) -> None:
        self.has_math_ocr = False
        self.math_ocr = None
        self._initialize_math_ocr()  # Try to initialize math-specific OCR first
        self._initialize_tesseract()  # Fallback for text regions

    def _initialize_math_ocr(self) -> None:
        """Initialize math-specific OCR (pix2tex) for better formula recognition."""
        try:
            # CRITICAL: Set environment variables BEFORE importing heavy libs
            # This prevents permission errors when libraries try to write to cache
            import tempfile
            import os
            
            temp_dir = tempfile.gettempdir()
            os.environ["TOKENIZERS_PARALLELISM"] = "false" # Prevent deadlocks
            os.environ["HF_HOME"] = os.path.join(temp_dir, "huggingface") 
            os.environ["TORCH_HOME"] = os.path.join(temp_dir, "torch")
            os.environ["TIMM_CACHE"] = os.path.join(temp_dir, "timm")
            
            log_debug(f"Initializing Math OCR in: {os.getcwd()}")
            log_debug(f"Temp dir: {temp_dir}")
            
            # DEBUG: Check critical dependencies explicitly
            try:
                import timm
                log_debug(f"Dependency check: timm imported successfully (version: {getattr(timm, '__version__', 'unknown')})")
            except ImportError as e:
                log_debug(f"Dependency check: FAILED to import timm: {e}")
                raise e # Re-raise to trigger fallback
            
            try:
                import einops
                log_debug(f"Dependency check: einops imported successfully")
            except ImportError as e:
                log_debug(f"Dependency check: FAILED to import einops: {e}")
                raise e

            try:
                import torchvision
                log_debug(f"Dependency check: torchvision imported successfully")
            except ImportError as e:
                log_debug(f"Dependency check: FAILED to import torchvision: {e}")
                # Don't raise, might work without it?

            # PRE-IMPORT Transformers to ensure it works
            try:
                import transformers
                log_debug(f"Dependency check: transformers imported successfully")
            except ImportError as e:
                log_debug(f"Dependency check: FAILED to import transformers: {e}")
                raise e

            from pix2tex.cli import LatexOCR
            import munch
            from utils.resource_utils import get_resource_path
            
            # Check for bundled model files (explicit bundle strategy)
            bundled_model_dir = get_resource_path("pix2tex_model")
            log_debug(f"Checking for bundled models at: {bundled_model_dir}")
            
            weights_path = os.path.join(bundled_model_dir, "weights.pth")
            config_path = os.path.join(bundled_model_dir, "config.yaml")
            tokenizer_path = os.path.join(bundled_model_dir, "tokenizer.json")
            resizer_path = os.path.join(bundled_model_dir, "image_resizer.pth")
            
            log_debug(f"Weights exists: {os.path.exists(weights_path)} ({weights_path})")
            
            if os.path.exists(weights_path) and os.path.exists(config_path):
                logger.info(f"[pix2tex] Found bundled model at: {bundled_model_dir}")
                log_debug("Loading bundled model...")
                
                # CRITICAL FIX FOR EXE:
                # pix2tex's LatexOCR overwrites CLI arguments with values from config.yaml!
                # Since config.yaml contains relative paths (e.g. "dataset/tokenizer.json"), 
                # this breaks in the frozen app where CWD is different.
                # We must create a temporary config file with ABSOLUTE paths.
                import yaml
                try:
                    with open(config_path, 'r') as f:
                        config_data = yaml.safe_load(f)
                    
                    # Force absolute paths in config
                    config_data['tokenizer'] = str(tokenizer_path)
                    # Also update valid/test data paths to avoid other errors
                    config_data['data'] = str(os.path.join(bundled_model_dir, "data_dummy.pkl")) 
                    config_data['valdata'] = str(os.path.join(bundled_model_dir, "val_dummy.pkl"))
                    
                    log_debug(f"Config data patch: tokenizer -> {config_data['tokenizer']}")
                    
                    # Verify tokenizer file actually exists and is readable
                    if os.path.exists(tokenizer_path):
                        try:
                            with open(tokenizer_path, 'r', encoding='utf-8') as tf:
                                head = tf.read(100)
                                log_debug(f"Tokenizer file check OK. Head: {head}...")
                        except Exception as te:
                            log_debug(f"Tokenizer file read FAILED: {te}")
                    else:
                        log_debug(f"Tokenizer file MISSING at: {tokenizer_path}")

                    # Create temp config
                    fd, temp_config_path = tempfile.mkstemp(suffix=".yaml", text=True)
                    with os.fdopen(fd, 'w') as f:
                        yaml.dump(config_data, f)
                    
                    log_debug(f"Created temp config at: {temp_config_path}")
                    
                    # Log the actual temp config content for verification
                    try:
                        with open(temp_config_path, 'r') as f:
                            temp_config_content = f.read()
                            log_debug(f"Temp config content:\n{temp_config_content}")
                    except Exception as e:
                        log_debug(f"Could not read temp config: {e}")
                    
                    args = munch.Munch({
                        'config': temp_config_path,
                        'checkpoint': weights_path,
                        'no_cuda': True,
                        'no_resize': False,
                        'tokenizer': tokenizer_path,
                        'image_resizer': resizer_path if os.path.exists(resizer_path) else None,
                    })
                    
                    log_debug(f"Initializing LatexOCR with args: tokenizer={args.tokenizer}, checkpoint={args.checkpoint}")
                    self.math_ocr = LatexOCR(arguments=args)
                    
                    # Verify what tokenizer path LatexOCR actually loaded
                    if hasattr(self.math_ocr, 'args') and hasattr(self.math_ocr.args, 'tokenizer'):
                        log_debug(f"LatexOCR loaded tokenizer from: {self.math_ocr.args.tokenizer}")
                    
                    log_debug(f"LatexOCR initialization SUCCESS. Model config: {self.math_ocr.args if hasattr(self.math_ocr, 'args') else 'unknown'}")
                    
                    # CRITICAL FIX: Force-reload tokenizer to fix garbage output in EXE
                    # pix2tex might be loading a cached/wrong tokenizer despite our config
                    try:
                        log_debug("Attempting to force-reload tokenizer...")
                        from tokenizers import Tokenizer
                        
                        # Load tokenizer directly from our bundled file
                        forced_tokenizer = Tokenizer.from_file(str(tokenizer_path))
                        log_debug(f"Force-loaded tokenizer from: {tokenizer_path}")
                        log_debug(f"Forced tokenizer vocab size: {forced_tokenizer.get_vocab_size()}")
                        
                        # Replace pix2tex's tokenizer with our correctly loaded one
                        if hasattr(self.math_ocr, 'tokenizer'):
                            old_vocab_size = len(self.math_ocr.tokenizer.get_vocab()) if hasattr(self.math_ocr.tokenizer, 'get_vocab') else 'unknown'
                            log_debug(f"Replacing pix2tex tokenizer (old vocab size: {old_vocab_size})")
                            self.math_ocr.tokenizer = forced_tokenizer
                            log_debug("Tokenizer force-reload SUCCESS")
                        else:
                            log_debug("WARNING: math_ocr has no tokenizer attribute to replace!")
                            
                    except Exception as tokenizer_reload_error:
                        log_debug(f"Tokenizer force-reload FAILED: {tokenizer_reload_error}")
                        # Continue anyway - maybe the original tokenizer works
                    
                    # Cleanup temp config
                    try:
                        os.unlink(temp_config_path)
                    except Exception:
                        pass
                        
                except Exception as config_exc:
                    log_debug(f"Failed to create temp config: {config_exc}. Falling back to default.")
                    # Fallback to original method (might fail)
                    args = munch.Munch({
                        'config': config_path,
                        'checkpoint': weights_path,
                        'tokenizer': tokenizer_path,
                        'no_cuda': True,
                        'no_resize': False,
                        'image_resizer': resizer_path if os.path.exists(resizer_path) else None,
                    })
                    self.math_ocr = LatexOCR(arguments=args)

            else:
                log_debug("Bundled model NOT found. Attempting fallback...")
                # Fallback to default behavior (user cache or package data)
                if getattr(sys, 'frozen', False):
                    # Trying to find it in implicit package bundle (PyInstaller _internal)
                    # For --onedir, sys._MEIPASS might look different or not be set directly
                    pass 
                
                self.math_ocr = LatexOCR()

            self.has_math_ocr = True
            logger.info("Math OCR (pix2tex) initialized successfully")
            
        except ImportError as ie:
            log_msg = f"ImportError during initialization: {ie}"
            log_debug(log_msg)
            self._write_debug_file("ocr_import_error.txt", log_msg)
            
            logger.warning(
                "pix2tex not available. Falling back to Tesseract."
            )
            self.has_math_ocr = False
            
        except Exception as exc:  # noqa: BLE001
            import traceback
            tb = traceback.format_exc()
            log_msg = f"CRITICAL ERROR initializing pix2tex: {exc}\n{tb}"
            log_debug(log_msg)
            self._write_debug_file("ocr_critical_error.txt", log_msg)
            
            logger.exception("Failed to initialize pix2tex. Using Tesseract fallback")
            self.has_math_ocr = False

    def _write_debug_file(self, filename, content):
        """Write debug info to user home/temp to ensure visibility."""
        import os
        import tempfile
        
        # Try temp dir first
        try:
            path = os.path.join(tempfile.gettempdir(), filename)
            with open(path, "w") as f:
                f.write(content)
            return
        except Exception:
            pass
            
        # Try home dir
        try:
            path = os.path.join(os.path.expanduser("~"), filename)
            with open(path, "w") as f:
                f.write(content)
        except Exception:
            pass


    def warm_up(self):
        """Warm up the OCR models with a dummy image to avoid cold-start lag."""
        if not self.has_math_ocr:
            return
        
        try:
            import numpy as np
            from PIL import Image
            logger.info("[OCR] Warming up models...")
            # Create a larger 100x100 image with non-uniform pixels
            # pix2tex/OpenCV can fail on empty/solid images during normalization
            dummy_img = Image.new('RGB', (100, 100), color='white')
            dummy_img.putpixel((0, 0), (0, 0, 0)) # Add one black pixel to ensure data.max() != data.min()
            
            # First call warms up the PyTorch model
            self.math_ocr(dummy_img)
            logger.info("[OCR] Warm-up complete")
        except Exception as e:
            logger.warning(f"[OCR] Warm-up failed: {e}")
    
    def _initialize_tesseract(self) -> None:
        """Initialize Tesseract path from settings."""
        # Reload settings to get latest config
        from core.config import settings
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
            logger.info("Tesseract initialized from settings: %s", settings.tesseract_cmd)
        else:
            # Try to find tesseract automatically
            import shutil
            tesseract_path = shutil.which("tesseract")
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                logger.info("Tesseract auto-detected: %s", tesseract_path)
            else:
                logger.warning("Tesseract OCR not found. OCR functionality will not work.")

    def image_to_latex(self, image_path: str | Path, handwriting_mode: bool = False, table_mode: bool = False) -> str:
        """Perform OCR on an image and return LaTeX-like text.
        
        Args:
            image_path: Path to the image file
            handwriting_mode: If True, bypass local OCR and force Vision API (better for handwriting)
            table_mode: If True, bypass local OCR and force Vision API (optimized for tables)
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"OCR image not found: {path}")
        
        logger.info("OCR on %s (Mode: %s)", path, "Handwriting/Vision" if handwriting_mode else "Standard")
        image = load_image(path)
        if image is None:
            raise ValueError(f"Could not open image for OCR: {path}")
        
        # Determine if we should use local OCR or bypass it
        # Bypass for handwriting OR tables (vision is much better for both)
        # ALSO bypass if API key is set - prevents pix2tex Tensor conversion error
        # (Local pix2tex has tokenizer force-reload issue causing: 'Tensor' object cannot be converted to 'Sequence')
        from core.config import settings as config_settings
        has_vision_api = bool(config_settings.openai_api_key)
        
        use_local_ocr = (
            self.has_math_ocr 
            and not handwriting_mode 
            and not table_mode
            and not has_vision_api  # Skip local OCR if Vision API is available
        )
        
        if has_vision_api and not handwriting_mode and not table_mode:
            logger.info("[OCR] OpenAI API key detected - using Vision API (avoids pix2tex Tensor error)")

        # Use math-specific OCR if available (much better for formulas)
        if use_local_ocr:
            try:
                logger.info("Using pix2tex for math OCR")
                # pix2tex expects PIL Image
                if isinstance(image, Image.Image):
                    pil_image = image
                else:
                    pil_image = Image.fromarray(image)
                
                # Convert to RGB if needed
                if pil_image.mode != 'RGB':
                    pil_image = pil_image.convert('RGB')
                
                # ACCURACY FIX: Add padding!
                # pix2tex (ViT) often fails if text touches the border. 
                # Adding 20-30px white padding improves accuracy significantly.
                from PIL import ImageOps
                pil_image = ImageOps.expand(pil_image, border=30, fill='white')
                
                latex_result = self.math_ocr(pil_image)
                
                # CRITICAL DEBUG: Log the raw output from pix2tex
                log_debug(f"pix2tex raw output: {latex_result}")
                log_debug(f"pix2tex output length: {len(latex_result) if latex_result else 0}")
                log_debug(f"pix2tex output type: {type(latex_result)}")
                
                # Check if tokenizer is accessible
                if hasattr(self.math_ocr, 'tokenizer'):
                    log_debug(f"Tokenizer vocab size: {len(self.math_ocr.tokenizer.get_vocab()) if hasattr(self.math_ocr.tokenizer, 'get_vocab') else 'unknown'}")
                else:
                    log_debug("WARNING: math_ocr has no tokenizer attribute!")
                
                logger.info("pix2tex result: %s", latex_result[:100])
                
                # Post-process the result
                logger.debug("[OCR] Before post-processing: %s", latex_result[:100])
                processed = self._post_process_ocr(latex_result)
                logger.debug("[OCR] After post-processing: %s", processed[:100])
                
                # Try OpenAI cleanup if corrupted and API key is available
                before_cleanup = processed
                processed = self._try_openai_ocr_cleanup(processed)
                if processed != before_cleanup:
                    logger.debug("[OCR] After OpenAI cleanup: %s", processed[:100])
                
                # Check if result is clean
                from services.ocr.pipeline_components import is_semantically_clean_latex
                is_clean = is_semantically_clean_latex(processed)
                
                # Check Turbo Mode DYNAMICALLY (allow user to toggle mid-run)
                from core.config import settings
                if settings.turbo_mode:
                    logger.info("[OCR] [Turbo] Skipping retries and fallbacks (Dynamic Check)")
                    return processed
                
                if is_clean:
                    logger.info("[OCR] Final LaTeX output: %s", processed[:100])
                    return processed
                
                # SAFETY: Do not 2x scale if the image is already large (prevents CPU hang)
                if pil_image.width > 800 or pil_image.height > 400:
                    logger.warning("[OCR] Image already large (%dx%d). Skipping 2x scale.", pil_image.width, pil_image.height)
                else:
                    logger.warning("[OCR] Corrupted/truncated. Retrying with 2x scaling...")
                    scaled_image = pil_image.resize(
                        (pil_image.width * 2, pil_image.height * 2), 
                        Image.Resampling.LANCZOS
                    )
                    retry_latex = self.math_ocr(scaled_image)
                    retry_processed = self._post_process_ocr(retry_latex)
                    if is_semantically_clean_latex(retry_processed):
                        logger.info("[OCR] ✅ Retry SUCCESSFUL")
                        return retry_processed
                    processed = retry_processed

                # FALLBACK: Try GPT-4o Vision
                logger.warning("[OCR] Attempting GPT-4 Vision Fallback...")
                vision_result = self._try_openai_vision_fallback(pil_image, table_mode=table_mode, handwriting_mode=handwriting_mode)
                if vision_result:
                    logger.info("[OCR] 🤖 Vision successful")
                    return self._post_process_ocr(vision_result)
                
                return processed
            except Exception as exc:  # noqa: BLE001
                logger.warning("pix2tex failed, falling back to Tesseract: %s", exc)
                # Fall through to Tesseract
        
                # Fall through to Tesseract
        
        # If Handwriting Mode was active, we skipped the `if use_local_ocr` block above.
        # So we arrive here. We must ensure we trigger the Vision fallback.
        
        if handwriting_mode or table_mode:
             logger.info("[OCR] Specialized Mode active (Handwriting/Table) - Forcing GPT-4o Vision directly")
             # Ensure we have a PIL image
             if isinstance(image, Image.Image):
                 hw_pil = image
             else:
                 hw_pil = Image.fromarray(image)
             
             vision_res = self._try_openai_vision_fallback(hw_pil, table_mode=table_mode, handwriting_mode=handwriting_mode)
             if vision_res:
                 logger.info("[OCR] 🤖 Vision (Handwriting) successful")
                 return self._post_process_ocr(vision_res)
             else:
                 logger.warning("[OCR] Vision failed in Handwriting Mode. Proceeding to Tesseract.")

        # ------------------------------------------------------------------
        # FALLBACK: Try GPT-4o Vision BEFORE Tesseract
        # Tesseract is poor at math; Vision is excellent.
        # ------------------------------------------------------------------
        try:
            # Ensure we have a PIL image
            if isinstance(image, Image.Image):
                fallback_pil = image
            else:
                fallback_pil = Image.fromarray(image)
            
            vision_res = self._try_openai_vision_fallback(fallback_pil)
            if vision_res:
                logger.info("[OCR] 🤖 Vision Fallback successful (avoiding Tesseract)")
                return self._post_process_ocr(vision_res)
        except Exception as vision_exc:
            logger.warning("[OCR] Vision fallback check failed: %s", vision_exc)

        # Fallback to Tesseract for text or if pix2tex unavailable
        logger.info("Using Tesseract OCR (fallback)")
        
        # Check if Tesseract is available
        try:
            pytesseract.get_tesseract_version()
        except Exception as exc:
            error_msg = (
                "Neither pix2tex nor Tesseract OCR is available.\n\n"
                "For math formulas, install pix2tex: pip install pix2tex[api]\n"
                "For text regions, install Tesseract:\n"
                "1. Go to Settings (in the sidebar) and select the Tesseract path\n"
                "2. Or download from: https://github.com/UB-Mannheim/tesseract/wiki\n"
                "3. Or use chocolatey: choco install tesseract\n\n"
                "After installation, use Settings to select the tesseract.exe path."
            )
            raise RuntimeError(error_msg) from exc
        
        # Build candidate images: preprocessed, original, inverted
        candidates = []
        try:
            preprocessed = self._preprocess_image(image)
            candidates.append(preprocessed)
        except Exception as prep_exc:  # noqa: BLE001
            logger.warning("Preprocess failed, using original image: %s", prep_exc)
        
        # Original image as PIL
        if isinstance(image, Image.Image):
            original_pil = image
        else:
            original_pil = Image.fromarray(image)
        candidates.append(original_pil)
        
        # Inverted (can help if thresholding removed strokes)
        try:
            inverted = ImageOps.invert(original_pil.convert("RGB"))
            candidates.append(inverted)
        except Exception:
            pass
        
        # Try different PSM modes for better formula recognition
        # PSM 6: Assume uniform block of text
        # PSM 7: Treat image as single text line
        # PSM 8: Treat image as single word
        # PSM 11: Sparse text (good for formulas)
        psm_modes = ["--psm 11", "--psm 7", "--psm 6", "--psm 8"]
        best_result = ""
        
        for cand_idx, cand in enumerate(candidates):
            for psm in psm_modes:
                try:
                    text = pytesseract.image_to_string(cand, config=psm)
                    if text and len(text.strip()) > len(best_result.strip()):
                        best_result = text.strip()
                        logger.debug("New best OCR (candidate %d, %s): %s", cand_idx, psm, best_result[:80])
                except Exception:  # noqa: BLE001
                    continue
        
        if not best_result:
            # Fallback: try default config on original
            try:
                text = pytesseract.image_to_string(original_pil, config="").strip()
                best_result = text
            except Exception:
                best_result = ""
        
        # Post-process OCR output to improve LaTeX conversion
        cleaned = self._post_process_ocr(best_result)
        
        logger.info("OCR raw result: %s", best_result[:200] if best_result else "EMPTY")
        # Safely encode Unicode for logging
        try:
            cleaned_safe = cleaned[:200].encode('ascii', 'replace').decode('ascii') if cleaned else "EMPTY"
            logger.info("OCR cleaned result: %s", cleaned_safe)
        except Exception:  # noqa: BLE001
            logger.info("OCR cleaned result: [contains Unicode]")
        
        if not cleaned or cleaned.strip() == "" or cleaned == r"\text{No text detected}":
            logger.warning("OCR returned empty or 'No text detected' for image: %s", path)
            logger.warning("Raw OCR result was: %s", best_result[:200] if best_result else "EMPTY")
            
            # Save debug image to help diagnose - check if crop is correct
            try:
                debug_path = path.parent / f"{path.stem}_debug_original.png"
                original_pil.save(str(debug_path))
                logger.info("💾 Saved debug image to: %s (verify crop region is correct)", debug_path)
            except Exception as debug_exc:  # noqa: BLE001
                logger.debug("Could not save debug image: %s", debug_exc)
            
            # Try one more time with original image scaled up significantly (formulas need high resolution)
            try:
                scaled = original_pil.resize(
                    (original_pil.width * 3, original_pil.height * 3),
                    Image.Resampling.LANCZOS
                )
                retry_text = pytesseract.image_to_string(scaled, config="--psm 11").strip()
                if retry_text and len(retry_text) > 0:
                    logger.info("Retry OCR with 3x scaling succeeded: %s", retry_text[:100])
                    cleaned_retry = self._post_process_ocr(retry_text)
                    if cleaned_retry and cleaned_retry != r"\text{No text detected}":
                        # Try OpenAI cleanup on retry result
                        cleaned_retry = self._try_openai_ocr_cleanup(cleaned_retry)
                        return cleaned_retry
            except Exception as retry_exc:  # noqa: BLE001
                logger.warning("Retry OCR with scaling failed: %s", retry_exc)
        
        # Final OpenAI cleanup if corrupted
        if cleaned:
            cleaned = self._try_openai_ocr_cleanup(cleaned)
        
        return cleaned if cleaned else r"\text{OCR failed}"
    
    def _preprocess_image(self, image) -> any:  # noqa: ANN401
        """Preprocess image to improve OCR accuracy for formulas."""
        from PIL import Image
        import cv2
        import numpy as np
        
        # Convert PIL Image to numpy array if needed
        if isinstance(image, Image.Image):
            image = np.array(image)
        
        # If image is very small, scale it up first (before other processing)
        height, width = image.shape[:2]
        if height < 50 or width < 50:
            scale = max(100 / height, 100 / width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            if len(image.shape) == 3:
                image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            else:
                image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        
        # Light contrast enhancement (less aggressive)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Light denoising (less aggressive to preserve text)
        denoised = cv2.fastNlMeansDenoising(enhanced, None, 5, 7, 21)
        
        # Use adaptive threshold instead of global - better for varying lighting
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Scale up if still too small (improves OCR accuracy)
        height, width = binary.shape
        if height < 100 or width < 100:
            scale = max(200 / height, 200 / width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            binary = cv2.resize(binary, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
        
        # Convert back to PIL Image for pytesseract
        return Image.fromarray(binary)
    
    def _post_process_ocr(self, text: str) -> str:
        """
        Minimal post-processing to preserve OCR fidelity.
        
        ARCHITECTURAL CHANGE:
        We no longer do aggressive regex replacements (like sum -> \\sum or alpha -> \\alpha) here.
        Rationale:
        1. pix2tex usually produces correct LaTeX tokens.
        2. "Fixing" logic often corrupts valid input (e.g. variable "alpha" becoming "\alpha").
        3. Semantic repairs are now handled by the StrictMathpixPipeline's AI layer.
        """
        if not text or not text.strip():
            logger.warning("OCR returned empty text")
            return r"\text{No text detected}"
        
        # Remove extra whitespace (but preserve newlines for structure)
        # Old: text = " ".join(text.split()) -> flattens newlines
        import re
        # Collapse multiple spaces/tabs to single space
        text = re.sub(r'[ \t]+', ' ', text)
        # Collapse multiple newlines to single newline
        text = re.sub(r'\n+', '\n', text)
        text = text.strip()
        
        logger.debug("Post-processing OCR text: %s", text[:100])
        
        # Basic filter for obvious gibberish (e.g. extremely long strings with no math symbols)
        if len(text) > 50 and " " not in text and "\\" not in text:
             # Long contiguous string without spaces or backslashes is likely garbage
             logger.warning("OCR output looks like noise (long contiguous string): %s...", text[:20])
        
        return text
    
    def _reconstruct_latex_from_ocr(self, text: str) -> str:
        """Reconstruct valid LaTeX from corrupted OCR using dynamic general patterns."""
        try:
            from services.ocr.dynamic_latex_reconstructor import DynamicLaTeXReconstructor
            reconstructor = DynamicLaTeXReconstructor()
            return reconstructor.reconstruct(text)
        except ImportError:
            # Fallback to old reconstructor if dynamic one not available
            try:
                from services.ocr.latex_reconstructor import LaTeXReconstructor
                reconstructor = LaTeXReconstructor()
                return reconstructor.reconstruct(text)
            except Exception as exc:  # noqa: BLE001
                logger.warning("LaTeX reconstruction failed, using basic cleaning: %s", exc)
                return self._basic_clean_ocr(text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Dynamic LaTeX reconstruction failed, using basic cleaning: %s", exc)
            # Fallback to basic cleaning
            return self._basic_clean_ocr(text)
    
    def _basic_clean_ocr(self, text: str) -> str:
        """Basic fallback cleaning."""
        import re
        # Remove common invalid characters
        invalid = ["€", "¥", "¢", "é", "É", "à", "è", "ù", "ô", "î", "ç", "ñ"]
        for char in invalid:
            text = text.replace(char, "")
        # Fix repeated operators
        text = text.replace("++", "+")
        text = text.replace("--", "-")
        return text.strip()
    
    def _clean_ocr_errors(self, text: str) -> str:
        """Clean common OCR errors from LaTeX text.
        
        CRITICAL: Do NOT corrupt valid LaTeX commands like \\left, \\right, \\sum, etc.
        Only fix obvious OCR errors (special characters, accented chars, etc.)
        """
        import re
        
        # CRITICAL: Check if text contains valid LaTeX commands - if so, be very careful
        has_valid_commands = bool(re.search(r'\\[a-zA-Z]+\{', text) or re.search(r'\\left|\\right|\\sum|\\mathbb|\\mathrm', text))
        
        # Common OCR error patterns (only fix obvious errors, not valid LaTeX)
        ocr_patterns = [
            # Remove currency symbols (not used in math)
            (r"€", ""),  # Euro symbol
            (r"¢", ""),  # Cent symbol
            (r"£", ""),  # Pound symbol
            (r"¥", ""),  # Yen symbol
            (r"»", ""),  # Right angle quote
            (r"«", ""),  # Left angle quote
            # Fix accented characters in math context (but NOT if part of valid command)
            # Only replace if NOT preceded by backslash (not a command)
            (r"(?<!\\)é", "e"),  # Accented e (not in command)
            (r"(?<!\\)É", "E"),  # Accented E (not in command)
            (r"(?<!\\)à", "a"),  # Accented a (not in command)
            (r"(?<!\\)è", "e"),  # Accented e (not in command)
            (r"(?<!\\)ù", "u"),  # Accented u (not in command)
            (r"(?<!\\)ô", "o"),  # Accented o (not in command)
            (r"(?<!\\)î", "i"),  # Accented i (not in command)
            (r"(?<!\\)ç", "c"),  # Cedilla c (not in command)
            (r"(?<!\\)ñ", "n"),  # Tilde n (not in command)
        ]
        
        # Apply OCR pattern fixes (only if text doesn't have valid commands, or very carefully)
        if not has_valid_commands:
            # Text doesn't have valid commands - safe to apply all fixes
            for pattern, replacement in ocr_patterns:
                try:
                    text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
                except re.error:
                    continue
        else:
            # Text has valid commands - only apply safe fixes (currency symbols, etc.)
            safe_patterns = [
                (r"€", ""), (r"¢", ""), (r"£", ""), (r"¥", ""), (r"»", ""), (r"«", ""),
            ]
            for pattern, replacement in safe_patterns:
                try:
                    text = re.sub(pattern, replacement, text)
                except re.error:
                    continue
        
        # Fix "i€E" → "i \in E" (only if not in valid command context)
        if not has_valid_commands:
            text = re.sub(r"i\s*€\s*E", lambda m: r"i \in E", text)
            text = re.sub(r"i\s*€\s*([A-Z])", lambda m: f"i \\in {m.group(1)}", text)
        
        # Remove standalone corrupted characters (non-printable or special)
        # But preserve valid LaTeX commands
        if not has_valid_commands:
            text = re.sub(r"[^\x20-\x7E\u00A0-\uFFFF]", "", text)  # Remove non-printable except common Unicode
        
        # Fix "iL(j)" → "i \in L(j)" or similar
        # Use lambda to avoid escape sequence issues
        text = re.sub(r"i\s*[^\w\s\[\](){}]\s*L\s*\(j\)", lambda m: r"i \in L(j)", text)
        text = re.sub(r"i\s*[^\w\s\[\](){}]\s*([A-Z])\s*\(j\)", lambda m: f"i \\in {m.group(1)}(j)", text)
        
        # Fix corrupted bracket patterns: "Y_{j}lé]" → "Y_{j}[l]"
        text = re.sub(r"([a-zA-Z])_\{([^}]+)\}l\s*[éèêë]\s*\]", r"\1_{\2}[l]", text)
        
        # Remove remaining stray special characters that aren't math symbols
        # Keep: + - * / = < > ( ) [ ] { } ^ _ \ and letters/numbers
        math_chars = set("+-*/=<>()[]{}^_\\")
        cleaned = []
        for char in text:
            if char.isalnum() or char in math_chars or char.isspace() or char in ".,;:!?":
                cleaned.append(char)
            elif char in "€¢£¥»«éÉàèùôîçñ":
                # Skip these - already handled above, but catch any remaining
                continue
            else:
                # Keep other characters (might be valid Unicode math symbols)
                cleaned.append(char)
        
        text = "".join(cleaned)
        
        # Final cleanup: remove multiple spaces (but preserve explicit structure if needed)
        # We want to treat newlines as line breaks for multiline equations
        # 1. Collapse horizontal whitespace
        text = re.sub(r"[ \t]+", " ", text)
        
        # 2. Convert newlines to LaTeX line breaks (double backslash)
        # But avoid double-double backslashes if already present
        # Check if we already have \\ followed by newline
        
        # Simple approach: Replace \n with \\ if it's not preceded by \\
        # But first collapse multiple newlines
        text = re.sub(r"[\r\n]+", "\n", text)
        
        # If we are NOT in an environment (simplistic check), we might want to force breaks.
        # But standard OCR might output:
        # x = y
        # a = b
        # We want: x = y \\ a = b
        
        # Replace newline with ' \\ ' ensuring we don't duplicate if already exists
        lines = text.split('\n')
        # Filter empty lines
        lines = [l.strip() for l in lines if l.strip()]
        
        lines = [l.strip() for l in lines if l.strip()]
        
        # 3. Heuristic: Split before enumeration markers like (i), (ii), (a) if they don't have breaks
        # This fixes cases where lists of equations are flattened
        # We process 'text' which is the joined version if we had lines, but here we operate on lines list or reconstructed text?
        # Let's operate on the text *before* converting newlines-to-breaks finalization, OR after re-joining.
        # Lines logic above handles explicit newlines. Now let's handle implicit ones in the lines.
        
        final_lines = []
        for line in lines:
            # Check for missing breaks before (i), (ii), (a), (b)
            # Regex lookbehind for space, lookahead for marker. Avoid variables like (x).
            # Markers: (i), (ii), ..., (vi), (a), (b), ... (e)
            # Use careful regex to replace ` <marker> ` with ` \\ <marker> `
            # Note: We avoid splitting if it seems to be part of a sentence like "in case (i)"
            # A simple safe heuristic: If the line is long and contains these markers, split.
            
            # Pattern: Space + (marker) + Space/Start of math
            # We use a substitution.
            # Markers: roman i-viii, alpha a-e.
            pattern = r"(?<!\\\\)\s+(\((?:[ivx]{1,4}|[a-e])\))(?=\s|[^a-zA-Z0-9])"
            # Replace with \\ \1
            line_processed = re.sub(pattern, r" \\\\ \1", line)
            
            final_lines.append(line_processed)
            
        lines = final_lines

        # Join with \\ if multiple lines found and no explicit structure detected?
        # Or just generally join them.
        if len(lines) > 1:
            # Check if headers already have \\ at end
            new_lines = []
            for i, line in enumerate(lines):
                 if i < len(lines) - 1 and not line.endswith(r'\\'):
                     new_lines.append(line + r" \\")
                 else:
                     new_lines.append(line)
            text = " ".join(new_lines)
        else:
            text = lines[0] if lines else ""

        # Remove any starting/ending spaces
        # Fix possible double backslashes from heuristic overlap
        text = text.replace(r"\\ \\", r"\\")
        text = text.replace(r"\\\\", r"\\")
        
        text = text.strip()
        
        return text
    
    def _try_openai_ocr_cleanup(self, ocr_text: str) -> str:
        """
        DEPRECATED: OpenAI should NOT be called at the OCR layer.
        
        According to the MANDATORY PIPELINE:
        1. OCR (Pix2Tex/Nougat) → LaTeX (RAW, no OpenAI)
        2. Regex + AST Corruption Gate → Clean LaTeX
        3. OpenAI (LaTeX ONLY, semantic rewrite) → Clean LaTeX (in strict pipeline)
        
        OpenAI cleanup should ONLY happen in the strict pipeline, not at the OCR layer.
        The OCR layer should return RAW LaTeX output only.
        """
        # 🚫 RULE: Do NOT call OpenAI at OCR layer
        # OpenAI semantic rewriting should happen in strict_pipeline.py only
        # This method now returns raw OCR output immediately - no OpenAI calls
        return ocr_text

    def _try_openai_vision_fallback(self, image, table_mode: bool = False, handwriting_mode: bool = False) -> str | None:
        """
        FALLBACK: Use GPT-4o Vision when local OCR fails completely.
        This provides a safety net for complex equations that pix2tex misses.
        """
        try:
            from services.ai.openai_mathml import OpenAIMathMLConverter
            
            # Check if API key is available (it's loaded in OpenAIMathMLConverter)
            import os
            if not os.getenv("OPENAI_API_KEY"):
                return None
                
            converter = OpenAIMathMLConverter()
            return converter.convert_image_to_latex(image, table_mode=table_mode, handwriting_mode=handwriting_mode)
        except ImportError:
            return None
        except Exception:
            return None
    
    def _is_corrupted_ocr_output(self, text: str) -> bool:
        """Detect if OCR output is corrupted (has shredded patterns)."""
        if not text:
            return False
        
        import re
        
        # Check for shredded command patterns like \e_{q}u_{i}v, \m_{a}t_{h}b_{f}
        shredded_patterns = [
            r'\\[a-z]_\{[a-z]\}[a-z]_\{[a-z]\}',  # \e_{q}u_{i} pattern
            r'\\[a-z]_\{[a-z]\}[a-z]_\{[a-z]\}[a-z]_\{[a-z]\}',  # \m_{a}t_{h}b_{f}
            r'\\[a-z]\s+[a-z]\s+[a-z]',  # Spaced commands like \ e q
            r'[a-z]_\{[a-z]\}[a-z]_\{[a-z]\}',  # Without backslash: e_{q}u_{i}
        ]
        
        for pattern in shredded_patterns:
            if re.search(pattern, text):
                return True
        
        # Check for many single-letter subscripts in a row (indicates corruption)

    def _calculate_basic_quality(self, latex: str) -> float:
        """
        Calculate a basic quality score for LaTeX to choose between attempts.
        Higher is better.
        """
        score = 0
        if not latex:
            return -100
            
        # 1. Balance check (most important)
        open_braces = latex.count('{')
        close_braces = latex.count('}')
        if open_braces == close_braces:
            score += 50
        else:
            score -= abs(open_braces - close_braces) * 5
            
        left_count = latex.count(r'\left')
        right_count = latex.count(r'\right')
        if left_count == right_count:
            score += 30
        else:
            score -= abs(left_count - right_count) * 10
            
        # 2. End validity
        if latex.strip().endswith('}'):
            score += 10
        if latex.strip().endswith(('\\', '_', '^')):
            score -= 20
            
        # 3. Length (heuristic: longer is often better if not noise)
        score += min(len(latex) / 10, 20)
        
        return score


