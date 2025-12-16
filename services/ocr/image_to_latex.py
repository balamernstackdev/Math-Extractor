"""Image to LaTeX OCR service."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytesseract
from PIL import Image, ImageOps

from core.config import settings
from core.logger import logger
from utils.image_utils import load_image


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
            from pix2tex.cli import LatexOCR
            import sys
            import os
            
            # Handle PyInstaller executable path resolution
            if getattr(sys, 'frozen', False):
                # Running as executable - ensure pix2tex can find models
                base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
                logger.info(f"[pix2tex] Running as executable, base_path: {base_path}")
                
                # Set environment variable for pix2tex cache if needed
                cache_dir = os.path.expanduser('~/.cache/pix2tex')
                if not os.path.exists(cache_dir):
                    # Try to use bundled models
                    bundled_cache = os.path.join(base_path, '.cache', 'pix2tex')
                    if os.path.exists(bundled_cache):
                        os.environ['PIX2TEX_CACHE'] = bundled_cache
                        logger.info(f"[pix2tex] Using bundled cache: {bundled_cache}")
            
            self.math_ocr = LatexOCR()
            self.has_math_ocr = True
            logger.info("Math OCR (pix2tex) initialized successfully")
        except ImportError:
            logger.warning(
                "pix2tex not available. Install with: pip install pix2tex[api]\n"
                "Falling back to Tesseract (not recommended for math formulas)"
            )
            self.has_math_ocr = False
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to initialize pix2tex: %s. Using Tesseract fallback", exc)
            self.has_math_ocr = False
    
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

    def image_to_latex(self, image_path: str | Path) -> str:
        """Perform OCR on an image and return LaTeX-like text."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"OCR image not found: {path}")
        
        logger.info("OCR on %s", path)
        image = load_image(path)
        if image is None:
            raise ValueError(f"Could not open image for OCR: {path}")
        
        # Use math-specific OCR if available (much better for formulas)
        if self.has_math_ocr:
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
                
                latex_result = self.math_ocr(pil_image)
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
                
                logger.info("[OCR] Final LaTeX output: %s", processed[:100])
                return processed
            except Exception as exc:  # noqa: BLE001
                logger.warning("pix2tex failed, falling back to Tesseract: %s", exc)
                # Fall through to Tesseract
        
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
        """Post-process OCR output to improve LaTeX conversion."""
        import re  # Import at the top of the function
        
        if not text or not text.strip():
            logger.warning("OCR returned empty text")
            return r"\text{No text detected}"
        
        # Remove extra whitespace and normalize
        text = " ".join(text.split())
        text = text.strip()
        
        # Log what we got from OCR
        logger.debug("Post-processing OCR text: %s", text[:100])
        
        # Check if LaTeX is already clean before reconstruction
        # If clean, skip reconstruction to avoid corrupting it
        original_text = text  # Keep original for comparison
        try:
            from services.ocr.strict_pipeline import is_semantically_clean_latex
            is_clean = is_semantically_clean_latex(text)
            logger.info("[OCR] Clean LaTeX check: is_clean=%s, text preview: %s", is_clean, text[:80])
            if is_clean:
                logger.info("[OCR] ✅ LaTeX is already clean, skipping reconstruction to avoid corruption")
                # Still do basic cleaning (remove stray characters) but skip reconstruction
                text = self._clean_ocr_errors(text)
                logger.info("[OCR] After basic cleaning: %s", text[:80])
            else:
                # LaTeX is corrupted - reconstruct it
                logger.info("[OCR] ⚠️ LaTeX is corrupted, attempting reconstruction")
                text = self._reconstruct_latex_from_ocr(text)
                logger.info("[OCR] After reconstruction: %s", text[:80])
                # Clean OCR errors after reconstruction
                text = self._clean_ocr_errors(text)
        except ImportError:
            # Fallback: if strict_pipeline not available, always reconstruct
            logger.warning("[OCR] Strict pipeline not available, using reconstruction (may corrupt clean LaTeX)")
            text = self._reconstruct_latex_from_ocr(text)
            # Clean OCR errors after reconstruction
            text = self._clean_ocr_errors(text)
        except Exception as exc:
            logger.error("[OCR] Error checking if LaTeX is clean: %s", exc)
            # On error, skip reconstruction to be safe
            logger.info("[OCR] Error occurred, skipping reconstruction to avoid corruption")
            text = self._clean_ocr_errors(original_text)
        
        # If it has many uppercase letters in a row or looks like random characters
        if len(text) > 10:
            uppercase_ratio = sum(1 for c in text if c.isupper()) / len(text)
            if uppercase_ratio > 0.7 and not any(c in text for c in "=+-*/()[]{}"):
                # Likely OCR error - treat as plain text
                logger.warning("OCR output looks like gibberish: %s", text[:50])
        
        # Check if text contains mathematical notation
        has_math_chars = any(char in text for char in "=+-*/()[]{}^_∑∫∏√≤≥≠≈±×÷")
        has_numbers = any(char.isdigit() for char in text)
        
        # If it's plain text without math symbols, wrap in \text{}
        if not has_math_chars:
            # It's regular text, not a formula
            # Escape special LaTeX characters
            text_escaped = text.replace("\\", "\\textbackslash")
            text_escaped = text_escaped.replace("{", "\\{")
            text_escaped = text_escaped.replace("}", "\\}")
            text_escaped = text_escaped.replace("$", "\\$")
            text_escaped = text_escaped.replace("&", "\\&")
            text_escaped = text_escaped.replace("%", "\\%")
            text_escaped = text_escaped.replace("#", "\\#")
            text_escaped = text_escaped.replace("^", "\\textasciicircum")
            text_escaped = text_escaped.replace("_", "\\_")
            text_escaped = text_escaped.replace("~", "\\textasciitilde")
            return f"\\text{{{text_escaped}}}"
        
        # Check if LaTeX already has proper commands (like \equiv, \sum, \mathbb)
        # If so, skip the regex substitutions that might corrupt it
        has_proper_commands = bool(re.search(r'\\[a-zA-Z]+\{', text) or re.search(r'\\[a-zA-Z]+(?:\[|\{|\(|$)', text))
        
        # Has math characters - try to convert to proper LaTeX
        # BUT: Skip regex substitutions if LaTeX already has proper commands (to avoid corruption)
        if not has_proper_commands:
            # Only apply regex substitutions if LaTeX doesn't have proper commands
            # (This prevents corrupting clean LaTeX from OCR)
            try:
                # Fractions: a/b -> \frac{a}{b} (but be careful with dates like 2/3/2024)
                fraction_pattern = r"(\d+|\w+)/(\d+|\w+)"
                if re.search(fraction_pattern, text) and not re.search(r"\d+/\d+/\d+", text):
                    text = re.sub(fraction_pattern, r"\\frac{\1}{\2}", text)
                
                # Subscripts: x_i -> x_{i} or x1 -> x_{1}
                # BUT: Don't match if there's a backslash before (it's a command)
                subscript_pattern = r"([a-zA-Z])(?<!\\)_?(\d+|[a-zA-Z])"
                text = re.sub(subscript_pattern, r"\1_{\2}", text)
                
                # Superscripts: x^2 -> x^{2} or x2 (if followed by space or end)
                superscript_pattern = r"(\w+)\^(\d+|\w+)"
                text = re.sub(superscript_pattern, r"\1^{\2}", text)
                
                # Summation: sum -> \sum (use lambda to avoid backreference issues)
                text = re.sub(r"\bsum\b", lambda m: r"\\sum", text, flags=re.IGNORECASE)
                
                # Integrals: int -> \int (use lambda to avoid backreference issues)
                text = re.sub(r"\bint\b", lambda m: r"\\int", text, flags=re.IGNORECASE)
                
                # Greek letters - use lambda to avoid regex backreference issues
                greek_map = {
                    "alpha": "\\alpha", "beta": "\\beta", "gamma": "\\gamma",
                    "delta": "\\delta", "epsilon": "\\epsilon", "theta": "\\theta",
                    "lambda": "\\lambda", "mu": "\\mu", "pi": "\\pi", "sigma": "\\sigma",
                    "phi": "\\phi", "omega": "\\omega"
                }
                for greek, latex in greek_map.items():
                    # Use lambda to avoid regex backreference parsing issues
                    pattern = rf"\b{re.escape(greek)}\b"
                    text = re.sub(pattern, lambda m, rep=latex: rep, text, flags=re.IGNORECASE)
            except re.error as regex_err:
                logger.warning("Regex error during post-processing: %s. Text: %s", regex_err, text[:100])
                # Return text as-is if regex fails
                pass
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error during post-processing: %s. Text: %s", exc, text[:100])
                # Return text as-is if processing fails
                pass
        else:
            logger.info("[OCR] LaTeX has proper commands, skipping regex substitutions to avoid corruption")
        
        # Wrap in math mode if not already LaTeX command
        if not text.startswith("$") and not text.startswith("\\") and has_math_chars:
            text = f"${text}$"
        
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
        
        # Final cleanup: remove multiple spaces
        text = re.sub(r"\s+", " ", text)
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
        if re.search(r'[a-z]_\{[a-z]\}[a-z]_\{[a-z]\}[a-z]_\{[a-z]\}', text):
            return True
        
        return False

