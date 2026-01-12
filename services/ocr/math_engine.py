"""Image to LaTeX OCR service."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union
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
        self.init_error = None
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

            # CRITICAL: Monkey-patch pix2tex checkpoint path BEFORE LatexOCR import
            # pix2tex tries to write to its package directory which is read-only on Streamlit Cloud
            pix2tex_cache = os.path.join(temp_dir, "mathpix_cache", "pix2tex")
            os.makedirs(pix2tex_cache, exist_ok=True)
            
            try:
                # Import the checkpoint module and patch BOTH the path variable AND the download function
                import pix2tex.model.checkpoints.get_latest_checkpoint as ckpt_module
                
                # Save the original function
                original_download = ckpt_module.download_checkpoints
                original_path = getattr(ckpt_module, 'path', None)
                
                # Patch the path variable
                ckpt_module.path = pix2tex_cache
                
                # Create a wrapper that uses our custom path
                def patched_download_checkpoints(tag=None):
                    """Patched version that downloads to writable temp directory."""
                    import os
                    import requests
                    from tqdm import tqdm
                    
                    # Use our writable cache path
                    cache_path = pix2tex_cache
                    os.makedirs(cache_path, exist_ok=True)
                    
                    weights_file = os.path.join(cache_path, "weights.pth")
                    
                    # Check if already downloaded
                    if os.path.exists(weights_file) and os.path.getsize(weights_file) > 50_000_000:
                        log_debug(f"Using cached weights from: {weights_file}")
                        return weights_file
                    
                    # Download from GitHub
                    tag = tag or "v0.0.1"
                    url = f"https://github.com/lukas-blecher/LaTeX-OCR/releases/download/{tag}/weights.pth"
                    log_debug(f"Downloading pix2tex weights to: {weights_file}")
                    
                    try:
                        response = requests.get(url, stream=True, timeout=120)
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', 0))
                        
                        with open(weights_file, 'wb') as f:
                            with tqdm(total=total_size, unit='B', unit_scale=True, desc="weights.pth") as pbar:
                                for chunk in response.iter_content(chunk_size=8192):
                                    f.write(chunk)
                                    pbar.update(len(chunk))
                        
                        log_debug(f"Successfully downloaded weights to: {weights_file}")
                        return weights_file
                    except Exception as e:
                        log_debug(f"Failed to download weights: {e}")
                        raise
                
                # Replace the function in the module
                ckpt_module.download_checkpoints = patched_download_checkpoints
                log_debug(f"Patched pix2tex checkpoint path: {original_path} -> {pix2tex_cache}")
                
            except Exception as patch_err:
                log_debug(f"Could not patch pix2tex checkpoint path: {patch_err}")

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
                    try:
                        log_debug("Attempting to force-reload tokenizer...")
                        from tokenizers import Tokenizer
                        
                        # Load tokenizer directly from our bundled file
                        forced_tokenizer = Tokenizer.from_file(str(tokenizer_path))
                        log_debug(f"Force-loaded tokenizer from: {tokenizer_path}")
                        log_debug(f"Forced tokenizer vocab size: {forced_tokenizer.get_vocab_size()}")
                        
                    # Resolution: Monkey-patch the library's root path detection if possible
                    # Or simple approach: Just Create the dummy file it is looking for!
                    # Path: /home/adminuser/venv/lib/python3.13/site-packages/pix2tex/model/app.py
                    
                    try:
                        missing_file = os.path.join(base_path, 'model', 'app.py')
                        if not os.path.exists(missing_file):
                            log_debug(f"Creating dummy file at: {missing_file}")
                            # We might not have write permission to site-packages, but let's try
                            with open(missing_file, 'w') as f:
                                f.write("# Dummy file created by Math Extractor fix\n")
                    except Exception as e:
                        log_debug(f"Could not create dummy file: {e}. Attempting import hack.")
                        
                    # Plan B: The error likely comes from 'utils.get_resource_path' or similar inside pix2tex.
                    # We can try to initialize the Model directly instead of using LatexOCR wrapper class.
                    # But first, let's look at the traceback user provided: 
                    # It was "[Errno 2] No such file... app.py".
                    # This implies something is doing open(...) on that file. 
                            
                    except Exception as tokenizer_reload_error:
                        log_debug(f"Tokenizer force-reload FAILED: {tokenizer_reload_error}")
                    
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
                log_debug("Bundled model NOT found. Attempting fallback with cached weights...")
                # We know the patch above downloaded weights to pix2tex_cache
                cache_weights = os.path.join(pix2tex_cache, "weights.pth")
                
                if os.path.exists(cache_weights):
                    log_debug(f"Found cached weights at: {cache_weights}")
                    # Manually construct args to force loading from our cache
                    # Resolution: Manually generate config to avoid 'app.py' or missing file errors
                    import pix2tex
                    import yaml
                    base_path = os.path.dirname(pix2tex.__file__)
                    
                    # Attempt to locate tokenizer in site-packages
                    tokenizer_path = os.path.join(base_path, 'model', 'dataset', 'tokenizer.json')
                    if not os.path.exists(tokenizer_path):
                        log_debug(f"Tokenizer not found at {tokenizer_path}, checking alternate...")
                        tokenizer_path = os.path.join(base_path, 'tokenizer.json')
                    
                    log_debug(f"Using Tokenizer path: {tokenizer_path}")
                    
                    # Standard config for ViT-Hybrid (default pix2tex)
                    # We hardcode this to ensure stability against missing package files
                    config_dict = {
                        'backbone_layers': [2, 3, 7],
                        'channels': 1,
                        'dim': 256,
                        'encoder_structure': 'hybrid',
                        'decoder_args': {'attn_on_attn': True, 'cross_attend': True, 'num_head': 8, 'num_layers': 1},
                        'max_seq_len': 512,
                        'max_dimensions': [1024, 2048],
                        'min_dimensions': [32, 32],
                        'patch_size': 16,
                        'pad': False,
                        'tokenizer': str(tokenizer_path)
                    }
                    
                    # Write temp config
                    fd, temp_cfg = tempfile.mkstemp(suffix=".yaml", text=True)
                    with os.fdopen(fd, 'w') as f:
                        yaml.dump(config_dict, f)
                    
                    log_debug(f"Generated temp config at: {temp_cfg}")
                    
                    args = munch.Munch({
                        'config': temp_cfg, 
                        'checkpoint': cache_weights,
                        'no_cuda': True,
                        'no_resize': False
                    })
                    
                    self.math_ocr = LatexOCR(arguments=args) # Try original first
                    
                    # Cleanup later? (OS handles temp usually, but explicit is nice)
                    # We leave it for now to avoid premature deletion

            self.has_math_ocr = True
            logger.info("Math OCR (pix2tex) initialized successfully")
            
        except (ImportError, FileNotFoundError, Exception) as ie:
            # RETRY WITH DIRECT MODEL LOADING (Bypassing LatexOCR wrapper)
            log_debug(f"Standard initialization failed: {ie}. Attempting DIRECT load...")
            try:
                import torch
                from transformers import PreTrainedTokenizerFast
                from pix2tex.models.transformer import HybridViT
                from pix2tex.dataset.transforms import test_transform
                import cv2
                import numpy as np

                # reused variables from above: base_path, cache_weights, tokenizer_path
                log_debug("Initializing HybridViT directly...")
                
                # Default config for standard pix2tex
                # We use the same config as the temp one we tried to write
                model = HybridViT(
                    backbone_layers=[2, 3, 7],
                    channels=1,
                    dim=256,
                    decoder_args={'attn_on_attn': True, 'cross_attend': True, 'num_head': 8, 'num_layers': 1},
                    max_seq_len=512,
                    max_dimensions=[1024, 2048],
                    min_dimensions=[32, 32],
                    patch_size=16,
                    pad=False,
                )
                
                # Load weights
                device = 'cpu'
                model.load_state_dict(torch.load(cache_weights, map_location=device))
                model.to(device)
                model.eval()
                
                # Load tokenizer
                tokenizer = PreTrainedTokenizerFast(tokenizer_file=str(tokenizer_path))
                
                # Create a simple callable wrapper that mimics LatexOCR
                class DirectLatexOCR:
                    def __init__(self, model, tokenizer, transform):
                        self.model = model
                        self.tokenizer = tokenizer
                        self.transform = transform
                        self.device = 'cpu'
                        self.args = munch.Munch({'no_cuda': True}) # Dummy args for logging
                        
                    def __call__(self, img):
                        # Preprocess exactly how pix2tex does it
                        if isinstance(img, Image.Image):
                            if img.mode != 'RGB':
                                img = img.convert('RGB')
                            img = np.array(img)
                        
                        # Resize/Pad logic is already done in image_to_latex, but transform expects specific shape
                        # We used 'test_transform' which handles ToTensor and Normalize
                        # But wait, test_transform in pix2tex might expect specific args.
                        # Let's verify standard pipeline manually.
                        
                        # Manual transform: Grayscale -> Resize/Pad if needed -> Normalize
                        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
                        img = Image.fromarray(img)
                        
                        # Use the library transform
                        im = self.transform(image=np.array(img))['image'][:1]
                        im = im.unsqueeze(0).to(self.device)
                        
                        # Generate
                        with torch.no_grad():
                             encoded = self.model.encoder(im)
                             dec = self.model.decoder.generate(torch.LongTensor([self.model.decoder.bos_token]*1).to(self.device), self.model.max_seq_len, eos_token=self.model.decoder.eos_token, context=encoded, temperature=0.2)
                        
                        pred = self.tokenizer.decode(dec.detach().cpu().numpy()[0], skip_special_tokens=True)
                        return pred.strip()

                self.math_ocr = DirectLatexOCR(model, tokenizer, test_transform)
                self.has_math_ocr = True
                log_debug("DIRECT MODEL LOADING SUCCESSFUL!")
                
            except Exception as direct_err:
                 log_debug(f"Direct load also failed: {direct_err}")
                 import traceback
                 log_debug(traceback.format_exc())
                 
                 # Re-raise original error to trigger Tesseract fallback
                 self.init_error = f"Double Failure: {ie} -> {direct_err}"
                 raise ie


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

    def image_to_latex(self, image_path: Union[str, Path], handwriting_mode: bool = False, table_mode: bool = False) -> str:
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
        from core.config import settings as config_settings
        has_vision_api = bool(config_settings.openai_api_key)
        
        use_local_ocr = (
            self.has_math_ocr 
            and not handwriting_mode 
            and not table_mode
            # Fixed: checking has_vision_api here caused us to SKIP local OCR if a bad key was present.
            # We now ALWAYS prefer local OCR first, using Vision only as a fallback.
        )
        
        if has_vision_api and not use_local_ocr:
            logger.info("[OCR] Vision API preferred (Handwriting/Table mode)")

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
                
                # ACCURACY FIX: Mandatory Padding & Contrast for Math Models
                from PIL import ImageOps
                
                # 1. Add substantial padding (30px)
                pil_image = ImageOps.expand(pil_image, border=30, fill='white')
                
                # 2. Resize up if too small (Critical for small crop regions)
                if pil_image.height < 100:
                    scale = 2.0
                    if pil_image.height < 50: scale = 3.0
                    pil_image = pil_image.resize(
                        (int(pil_image.width * scale), int(pil_image.height * scale)), 
                        Image.Resampling.LANCZOS
                    )
                
                latex_result = self.math_ocr(pil_image)
                
                # CRITICAL DEBUG: Log the raw output from pix2tex
                log_debug(f"pix2tex raw output: {latex_result}")
                
                logger.info("pix2tex result: %s", latex_result[:100])
                
                # Post-process the result
                processed = self._post_process_ocr(latex_result)
                
                # Try OpenAI cleanup if corrupted and API key is available
                before_cleanup = processed
                processed = self._try_openai_ocr_cleanup(processed)
                if processed != before_cleanup:
                    logger.debug("[OCR] After OpenAI cleanup: %s", processed[:100])
                
                # Check if result is clean
                from services.ocr.pipeline_components import is_semantically_clean_latex
                is_clean = is_semantically_clean_latex(processed)
                
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
                import traceback
                tb = traceback.format_exc()
                log_debug(f"pix2tex inference CRASHED: {exc}\n{tb}")
                logger.warning("pix2tex failed, falling back to Tesseract: %s", exc)
                # Fall through to Tesseract
        
        # If Handwriting Mode was active, we skipped the `if use_local_ocr` block above.
        
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

        # Fallback to Tesseract
        logger.info("Using Tesseract OCR (fallback)")
        
        try:
            pytesseract.get_tesseract_version()
        except Exception as exc:
            error_msg = ("Tesseract not found. Please install Tesseract-OCR.")
            raise RuntimeError(error_msg) from exc
        
        # Tesseract execution (simplified due to size limit)
        if isinstance(image, Image.Image):
             original_pil = image
        else:
             original_pil = Image.fromarray(image)
        
        best_result = pytesseract.image_to_string(original_pil, config="--psm 11").strip()
        cleaned = self._post_process_ocr(best_result)
        
        if cleaned:
            cleaned = self._try_openai_ocr_cleanup(cleaned)
        
        final_output = (cleaned + r" \quad \text{[Tesseract]}") if cleaned else r"\text{OCR failed}"
        if self.init_error:
             final_output += f" \\quad \\text{{[Error: {self.init_error}]}}"
        return final_output
    
    def _preprocess_image(self, image) -> any:  # noqa: ANN401
        """Preprocess image to improve OCR accuracy."""
        from PIL import Image
        import cv2
        import numpy as np
        if isinstance(image, Image.Image):
            image = np.array(image)
        # Simplified preprocessing
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image
        return Image.fromarray(gray)
    
    def _post_process_ocr(self, text: str) -> str:
        """Minimal post-processing."""
        if not text:
            return r"\text{No text detected}"
        import re
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        return text.strip()
    
    def _reconstruct_latex_from_ocr(self, text: str) -> str:
        return text
    
    def _basic_clean_ocr(self, text: str) -> str:
        return text.strip()
    
    def _clean_ocr_errors(self, text: str) -> str:
        return text
    
    def _try_openai_ocr_cleanup(self, ocr_text: str) -> str:
        return ocr_text

    def _try_openai_vision_fallback(self, image, table_mode: bool = False, handwriting_mode: bool = False) -> Optional[str]:
        """
        FALLBACK: Use GPT-4o Vision when local OCR fails completely.
        """
        try:
            from services.ai.openai_mathml import OpenAIMathMLConverter
            from core.config import settings
            api_key = settings.openai_api_key
            if not api_key:
                import os
                api_key = os.getenv("OPENAI_API_KEY")
            
            if not api_key:
                return None
                
            converter = OpenAIMathMLConverter(api_key=api_key)
            return converter.convert_image_to_latex(image, table_mode=table_mode, handwriting_mode=handwriting_mode)
        except ImportError as ie:
            logger.warning(f"Validation Warning: OpenAI Vision Fallback failed (ImportError): {ie}")
            return None
        except Exception as e:
            logger.error(f"Validation Warning: OpenAI Vision Fallback failed (Exception): {e}")
            return None
    
    def _is_corrupted_ocr_output(self, text: str) -> bool:
        """
        Detect if OCR output is likely corrupted or low quality.
        Returns True if the output looks like garbage and should trigger fallback.
        """
        if not text or len(text.strip()) < 3:
            return True
            
        # 1. Check for unbalanced braces (strong indicator of broken latex)
        if text.count('{') != text.count('}'):
            # Allow small mismatch if complex, but generally bad
            if abs(text.count('{') - text.count('}')) > 1:
                logger.debug("[Corruption] Unbalanced braces")
                return True

        # 2. Check for high density of special garbage characters
        # Count non-ASCII, non-math symbols
        # Allowed: alphanumeric, space, \ { } ^ _ = + - * ( ) [ ]
        # We classify everything else as potentially 'noise' if in high ratio
        invalid_chars = 0
        total_chars = len(text)
        
        # Simple ASCII-safe check
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\\{}^_=+-*()[].,;:!? \n\t")
        for char in text:
            if char not in allowed:
                invalid_chars += 1
        
        error_ratio = invalid_chars / total_chars
        if error_ratio > 0.3: # More than 30% unrecognised chars
            logger.debug(f"[Corruption] High noise ratio: {error_ratio:.2f}")
            return True
            
        # 3. Check for specific garbage patterns (repeated chars)
        import re
        if re.search(r'(\D)\1{5,}', text): # Same non-digit char repeated 6+ times (e.g. "......")
            logger.debug("[Corruption] Repeated character pattern")
            return True
            
        return False
    
    def _calculate_basic_quality(self, latex: str) -> float:
        score = 0
        if not latex: return 0
        if "{" in latex and "}" in latex: score += 10
        return score

    def has_vision_fallback_configured(self) -> bool:
        from core.config import settings
        return bool(settings.openai_api_key)

