"""
OpenAI-based MathML and Equation Converter

Uses OpenAI API (GPT models) to convert corrupted MathML or LaTeX to clean formats.
Can be used as a fallback or enhancement to rule-based recovery.

Usage:
    from services.ocr.openai_mathml_converter import OpenAIMathMLConverter
    
    converter = OpenAIMathMLConverter(api_key="your-key")
    result = converter.convert_corrupted_mathml(corrupted_mathml)
    # or
    result = converter.convert_latex_to_mathml(latex_string)
"""

from __future__ import annotations

import os
import json
from typing import Dict, Optional, List
from core.logger import logger

try:
    from openai import OpenAI
    import httpx
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    httpx = None
    logger.warning("openai package not installed. Install with: pip install openai")


class OpenAIMathMLConverter:
    """Convert MathML/LaTeX using OpenAI API with specialized prompts."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize OpenAI MathML converter.
        
        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: Model to use (gpt-4o-mini, gpt-4o, gpt-3.5-turbo, etc.)
            base_url: Custom base URL (for Azure OpenAI or other providers)
            timeout: Request timeout in seconds
        """
        if not HAS_OPENAI:
            raise ImportError(
                "openai package required. Install with: pip install openai"
            )
        
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key parameter"
            )
        
        self.model = model
        self.timeout = timeout
        
        # Initialize OpenAI client
        # FIX: Create explicit httpx client to avoid 'proxies' parameter issue
        # The OpenAI library's internal httpx client tries to read proxies from env vars
        # and pass them through, but newer versions don't accept 'proxies' as a parameter
        # Solution: Create our own httpx client explicitly without proxies
        
        # Build base kwargs
        client_kwargs: dict = {
            "api_key": self.api_key
        }
        
        # Add base_url if provided (for Azure OpenAI or custom endpoints)
        if base_url:
            client_kwargs["base_url"] = base_url
        
        # Create explicit httpx client to avoid proxy issues
        # The OpenAI library's internal SyncHttpxClientWrapper tries to read proxies from env vars
        # and pass them through, but newer httpx versions don't accept 'proxies' as a parameter
        # Solution: Temporarily unset proxy env vars BEFORE creating httpx client
        httpx_timeout = timeout if timeout and timeout > 0 else 30.0
        
        # CRITICAL: Save and unset ALL proxy environment variables BEFORE any httpx/OpenAI code runs
        # This must happen before httpx.Client() is called, as it reads env vars at creation time
        proxy_env_vars = {}
        proxy_keys = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
        for key in proxy_keys:
            if key in os.environ:
                proxy_env_vars[key] = os.environ.pop(key)
        
        try:
            if httpx is not None:
                # Create httpx client AFTER unsetting proxy env vars
                # This ensures httpx doesn't read proxy settings from environment
                # Note: We don't pass proxies parameter at all - newer httpx versions don't accept it
                http_client = httpx.Client(
                    timeout=httpx_timeout,
                    # Explicitly don't pass proxies - let it be None/empty
                )
                client_kwargs["http_client"] = http_client
            
            # Now create OpenAI client (proxy env vars are unset, so SyncHttpxClientWrapper won't find them)
            # The OpenAI library will use our http_client, but if it tries to create SyncHttpxClientWrapper,
            # it won't find proxy env vars to pass through
            self.client = OpenAI(**client_kwargs)
            logger.info(f"OpenAI MathML converter initialized (model: {model})")
        except TypeError as e:
            error_str = str(e).lower()
            if "proxies" in error_str:
                # If proxies error still occurs, try with a custom httpx client that explicitly ignores proxies
                logger.warning(f"Proxies error detected, trying alternative approach: {e}")
                client_kwargs.pop("http_client", None)
                
                # Try creating httpx client with explicit proxy configuration
                if httpx is not None:
                    try:
                        # Create client with empty proxy config
                        http_client = httpx.Client(
                            timeout=httpx_timeout,
                            # Try to explicitly set proxies to empty dict if supported
                        )
                        # Try to disable proxy detection by setting env to empty
                        client_kwargs["http_client"] = http_client
                        self.client = OpenAI(**client_kwargs)
                        logger.info(f"OpenAI MathML converter initialized (model: {model}, alternative config)")
                    except Exception:
                        # Last resort: try without http_client
                        client_kwargs.pop("http_client", None)
                        self.client = OpenAI(**client_kwargs)
                        logger.info(f"OpenAI MathML converter initialized (model: {model}, minimal config)")
                else:
                    self.client = OpenAI(**client_kwargs)
                    logger.info(f"OpenAI MathML converter initialized (model: {model}, minimal config)")
            else:
                raise
        except Exception as e:
            # Fallback: try without explicit http_client if there's an issue
            logger.warning(f"Failed to create OpenAI client, trying fallback: {e}")
            client_kwargs.pop("http_client", None)
            try:
                self.client = OpenAI(**client_kwargs)
                logger.info(f"OpenAI MathML converter initialized (model: {model}, fallback config)")
            except Exception as e2:
                logger.error(f"Failed to initialize OpenAI client: {e2}")
                raise
        finally:
            # Restore proxy environment variables
            for key, value in proxy_env_vars.items():
                os.environ[key] = value
    
    def convert_corrupted_mathml(
        self,
        corrupted_mathml: str,
        target_format: str = "mathml",
        include_latex: bool = True
    ) -> Dict:
        """
        Convert corrupted MathML to clean format using AI.
        
        Args:
            corrupted_mathml: Corrupted MathML string
            target_format: "mathml" or "latex"
            include_latex: Whether to also return LaTeX representation
        
        Returns:
            {
                "mathml": "<clean MathML>",
                "latex": "<LaTeX representation>",
                "confidence": float,
                "log": [str, ...]
            }
        """
        log: List[str] = []
        
        prompt = self._build_mathml_recovery_prompt(
            corrupted_mathml, target_format, include_latex
        )
        
        try:
            log.append(f"Calling OpenAI API (model: {self.model})")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Low temperature for consistent output
                max_tokens=3000  # Increased for complex equations
            )
            
            content = response.choices[0].message.content
            log.append("Received response from OpenAI")
            
            # Parse the JSON response
            result = self._parse_ai_response(content, log)
            
            return {
                "mathml": result.get("mathml", ""),
                "latex": result.get("latex", ""),
                "confidence": result.get("confidence", 0.8),
                "log": log
            }
            
        except Exception as exc:
            logger.exception("OpenAI conversion failed")
            log.append(f"Error: {exc}")
            return {
                "mathml": "",
                "latex": "",
                "confidence": 0.0,
                "log": log
            }
    
    def convert_latex_to_mathml_strict(
        self,
        latex: str,
        context: Optional[str] = None
    ) -> Dict:
        """
        Convert LaTeX to MathML in STRICT mode (syntax fixes only, no paraphrasing).
        
        AI may ONLY:
        - validate syntax
        - fix broken braces
        - fix missing backslashes
        - fix malformed MathML tags
        
        AI must NOT paraphrase math.
        """
        log: List[str] = []
        
        prompt = self._build_latex_to_mathml_prompt(latex, context, strict_mode=True)
        
        try:
            log.append(f"Converting LaTeX to MathML in STRICT mode (model: {self.model})")
            
            # Wrap API call in try-except to catch any execution errors
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": self._get_system_prompt(strict_mode=True)
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0.0,  # Zero temperature for strict mode (deterministic)
                    max_tokens=3000
                )
                
                content = response.choices[0].message.content
                log.append("Received response from OpenAI (strict mode)")
            except NameError as name_err:
                # This catches "name 's_1' is not defined" type errors
                error_msg = str(name_err)
                log.append(f"CRITICAL: NameError during API call or response access: {error_msg}")
                log.append("This suggests OpenAI response contains executable code")
                logger.error(f"NameError in OpenAI API call: {error_msg}")
                # Return empty result - will be handled by fallback
                return {
                    "mathml": "",
                    "latex": latex,
                    "confidence": 0.0,
                    "log": log
                }
            
            # Parse response with additional safety
            try:
                result = self._parse_ai_response(content, log)
            except ValueError as json_err:
                # JSON-only violation - OpenAI returned markdown/prose instead of JSON
                error_msg = str(json_err)
                log.append(f"CRITICAL: OpenAI violated JSON-only requirement: {error_msg}")
                log.append("CRITICAL: OpenAI returned markdown/prose instead of JSON - REJECTING")
                logger.error(f"JSON-only violation in OpenAI response: {error_msg}")
                # Re-raise to let caller handle (don't return fallback - this encourages violations)
                raise
            except (NameError, SyntaxError) as parse_err:
                # If parsing triggers code execution, catch it here
                error_msg = str(parse_err)
                log.append(f"CRITICAL: Code execution error during parsing: {error_msg}")
                log.append("OpenAI response likely contains executable code")
                logger.error(f"Code execution error in response parsing: {error_msg}")
                # Return empty result - will use original LaTeX
                return {
                    "mathml": "",
                    "latex": latex,
                    "confidence": 0.0,
                    "log": log
                }
            
            return {
                "mathml": result.get("mathml", ""),
                "latex": result.get("latex", latex),
                "confidence": result.get("confidence", 0.9),
                "log": log
            }
            
        except (NameError, SyntaxError) as code_err:
            # Catch code execution errors specifically
            error_msg = str(code_err)
            log.append(f"CRITICAL: Code execution error: {error_msg}")
            logger.error(f"Code execution error in OpenAI conversion: {error_msg}")
            logger.error("This suggests OpenAI response contains executable Python code")
            return {
                "mathml": "",
                "latex": latex,
                "confidence": 0.0,
                "log": log
            }
        except ValueError:
            # Re-raise JSON-only violations - don't catch them here
            raise
        except Exception as exc:
            logger.exception("OpenAI LaTeX conversion failed (strict mode)")
            log.append(f"Error: {exc}")
            return {
                "mathml": "",
                "latex": latex,
                "confidence": 0.0,
                "log": log
            }
    
    def convert_latex_to_mathml(
        self,
        latex: str,
        context: Optional[str] = None
    ) -> Dict:
        """
        Convert LaTeX to clean MathML using AI.
        
        Args:
            latex: LaTeX string
            context: Optional context about the equation
        
        Returns:
            {
                "mathml": "<clean MathML>",
                "latex": "<cleaned LaTeX>",
                "confidence": float,
                "log": [str, ...]
            }
        """
        log: List[str] = []
        
        prompt = self._build_latex_to_mathml_prompt(latex, context)
        
        try:
            log.append(f"Converting LaTeX to MathML (model: {self.model})")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                max_tokens=3000  # Increased for complex equations
            )
            
            content = response.choices[0].message.content
            log.append("Received response from OpenAI")
            
            result = self._parse_ai_response(content, log)
            
            return {
                "mathml": result.get("mathml", ""),
                "latex": result.get("latex", latex),  # Return original if no cleaned version
                "confidence": result.get("confidence", 0.9),
                "log": log
            }
            
        except Exception as exc:
            logger.exception("OpenAI LaTeX conversion failed")
            log.append(f"Error: {exc}")
            return {
                "mathml": "",
                "latex": latex,
                "confidence": 0.0,
                "log": log
            }
    
    def _get_system_prompt(self, strict_mode: bool = False) -> str:
        """Get the system prompt for the AI assistant."""
        if strict_mode:
            return """You are a STRICT Math Validation & Fix Agent. Your task is LIMITED to syntax fixes only.

CRITICAL RULES (STRICT MODE - DO NOT VIOLATE):
1. NEVER split LaTeX macros into characters (e.g., e_{{q}}u_{{i}}v → \\equiv, NOT character-by-character)
2. NEVER rewrite math symbols unless syntax is invalid (e.g., \\mathbb{Z} stays \\mathbb{Z}, NOT "math b Z")
3. AI is NOT allowed to paraphrase math - you may ONLY:
   - validate syntax
   - fix broken braces {}
   - fix missing backslashes \\
   - fix malformed MathML tags
4. NEVER place formulas inside <mtext> tags
5. NEVER split math keywords into individual characters
6. Use semantic MathML tags: <mi>, <mo>, <msub>, <msup>, <mrow>, <munderover>, <msubsup>
7. For text subscripts like "error" in P_error, use <mtext>error</mtext> inside <msub> (ONLY valid use of <mtext>)

YOUR TASK:
- Fix ONLY syntax errors (braces, backslashes, malformed tags)
- Preserve ALL mathematical content exactly as-is
- Do NOT change mathematical meaning or structure
- Return PURE MathML with no explanation text

OUTPUT FORMAT:
Return JSON ONLY - no markdown, no explanations, no prose.
JSON format: {"mathml": "...", "latex": "...", "confidence": 0.0-1.0}
CRITICAL: Output MUST be valid JSON that can be parsed with json.loads()"""
        
        return """You are a Math Extraction & Validation Agent specialized in converting mathematical equations to clean LaTeX and proper Presentation MathML.

CRITICAL RULES (MUST FOLLOW):
1. NEVER place formulas inside <mtext> tags
2. NEVER split math keywords into individual characters (e.g., "error", "Pr", "bigcup" should be single entities)
3. Use semantic MathML tags: <mi>, <mo>, <msub>, <msup>, <mrow>, <munderover>, <msubsup>
4. Follow MathML standards exactly
5. For text subscripts like "error" in P_error, use <mtext>error</mtext> inside <msub> (this is the ONLY valid use of <mtext>)
6. Functions like Pr, error, bigcup must be treated as complete symbols, not character-by-character

Your task:
1. Reconstruct the correct equation from corrupted input
2. Produce canonical LaTeX
3. Convert LaTeX to valid Presentation MathML
4. Validate grouping, subscripts, operators, and functions

OUTPUT FORMAT:
Return JSON ONLY - no markdown, no explanations, no prose.
JSON format: {"mathml": "...", "latex": "...", "confidence": 0.0-1.0}
CRITICAL: Output MUST be valid JSON that can be parsed with json.loads()

MathML Requirements:
- Use proper namespace: xmlns="http://www.w3.org/1998/Math/MathML" display="inline" or display="block"
- For subscripts: <msub><mi>base</mi><mi>sub</mi></msub> or <msub><mi>P</mi><mtext>error</mtext></msub>
- For superscripts: <msup><mi>base</mi><mi>sup</mi></msup>
- For both: <msubsup><mo>operator</mo><mrow>lower</mrow><mi>upper</mi></msubsup>
- For operators: Use Unicode entities: &#x22C3; (∪), &#x2260; (≠), &#x2026; (…)
- Always wrap expressions in <mrow> for proper grouping
- Use <mi> for identifiers, <mn> for numbers, <mo> for operators
- Preserve all mathematical structure exactly

VALIDATION CHECKLIST:
✓ No <mtext> for equations (only for text subscripts like "error")
✓ No character-level subscripting of math keywords
✓ Functions like Pr, error, bigcup treated as complete symbols
✓ Readable by MathJax
✓ Equivalent to original equation"""
    
    def _build_mathml_recovery_prompt(
        self,
        corrupted_mathml: str,
        target_format: str,
        include_latex: bool
    ) -> str:
        """Build prompt for MathML recovery."""
        prompt = f"""You are a Math Extraction & Validation Agent. I have corrupted MathML from OCR that contains shredded LaTeX commands. You must reconstruct the correct equation and produce clean MathML.

Corrupted MathML:
```xml
{corrupted_mathml[:2000]}
```

CRITICAL: The corrupted input contains OCR errors. IGNORE its structure and reconstruct the math correctly.

Common corruption patterns to fix:
- Shredded commands: \\m_{{a}}t_{{h}}r_{{m}} → \\mathrm
- Letter-by-letter subscripts: e_{{r}}r_{{o}}r → "error" (complete word)
- Broken operators: \\l_{{e}}f_{{t}} → \\left, \\r_{{i}}g_{{h}}t → \\right
- Broken symbols: \\b_{{i}}g_{{c}}u_{{p}} → \\bigcup, \\n_{{e}}q → \\neq
- Broken dots: \\l_{{d}}o_{{t}}s → \\ldots

PROCESS:
Step 1: Visually/logically reconstruct the correct equation from the corrupted input
Step 2: Produce canonical LaTeX (e.g., P_{{\\mathrm{{error}}}}(C) = \\mathrm{{Pr}}\\left[\\bigcup_{{i=1}}^{{K}}\\{{W_i \\neq g_i(Y_{{d_i}}[0], \\ldots, Y_{{d_i}}[n-1])\\}}\\right])
Step 3: Convert LaTeX to valid Presentation MathML
Step 4: Validate grouping, subscripts, operators, and functions

CRITICAL RULES (MUST FOLLOW):
1. NEVER place formulas inside <mtext> tags
2. NEVER split math keywords into characters (e.g., "error", "Pr", "bigcup" must be complete)
3. Use semantic MathML: <mi>, <mo>, <msub>, <msup>, <mrow>, <munderover>, <msubsup>
4. For text subscripts like "error" in P_error, use <msub><mi>P</mi><mtext>error</mtext></msub>
5. Functions like Pr, error, bigcup must be treated as complete symbols

OUTPUT FORMAT (MANDATORY - JSON ONLY):
{"Provide both LaTeX and MathML" if include_latex else "Focus on MathML"}
Return JSON ONLY - no markdown, no explanations, no prose.
JSON format: {{"mathml": "...", {"latex": "...", " if include_latex else ""}"confidence": 0.0-1.0}}
CRITICAL: Output MUST be valid JSON that can be parsed with json.loads()
NO MARKDOWN CODE BLOCKS, NO EXPLANATIONS, NO PROSE - ONLY JSON

MathML Requirements:
- Well-formed XML: xmlns="http://www.w3.org/1998/Math/MathML" display="inline"
- Use correct tags: <mrow>, <mi>, <mo>, <msub>, <msup>, <msubsup>
- For text subscripts: <mtext>error</mtext> inside <msub> (ONLY valid use of <mtext>)
- For operators: Unicode entities: &#x22C3; (∪), &#x2260; (≠), &#x2026; (…)
- Proper grouping with <mrow>
- Readable by MathJax
- Equivalent to original equation

VALIDATION CHECKLIST:
✓ No <mtext> for equations (only for text subscripts)
✓ No character-level subscripting of math keywords
✓ Functions treated as complete symbols
✓ Readable by MathJax
✓ Equivalent to original equation"""
        
        return prompt
    
    def _build_latex_to_mathml_prompt(
        self,
        latex: str,
        context: Optional[str],
        strict_mode: bool = False
    ) -> str:
        """Build prompt for LaTeX to MathML conversion."""
        if strict_mode:
            prompt = f"""Fix ONLY syntax errors in the following LaTeX equation. Do NOT change mathematical content.

LaTeX:
```
{latex}
```

STRICT MODE RULES:
1. Fix ONLY: broken braces {{}}, missing backslashes \\, malformed structure
2. DO NOT: change mathematical symbols, rewrite equations, or paraphrase
3. Preserve ALL mathematical content exactly as-is
4. Convert to valid MathML with proper tags

"""
            if context:
                prompt += f"\nContext: {context}\n"
            
            prompt += """
OUTPUT:
Return JSON with keys: mathml, latex, confidence
- mathml: Valid MathML with syntax errors fixed
- latex: LaTeX with syntax errors fixed (if any)
- confidence: 0.0-1.0 based on syntax fix confidence

IMPORTANT: Only fix syntax, do NOT change mathematical meaning."""
            return prompt
        
        prompt = f"""Convert the following LaTeX equation to clean, well-formed MathML (ChatGPT-style quality).

LaTeX:
```
{latex}
```
"""
        if context:
            prompt += f"\nContext: {context}\n"
        
        prompt += """
CRITICAL RULES (MUST FOLLOW):
1. NEVER place formulas inside <mtext> tags
2. NEVER split math keywords into individual characters
3. Use semantic MathML tags: <mi>, <mo>, <msub>, <msup>, <mrow>, <munderover>, <msubsup>
4. Follow MathML standards exactly

PROCESS:
Step 1: Reconstruct the correct equation (ignore any corruption in input)
Step 2: Produce canonical LaTeX
Step 3: Convert LaTeX to valid Presentation MathML
Step 4: Validate grouping, subscripts, operators, and functions

MathML Requirements:
- Use proper namespace: xmlns="http://www.w3.org/1998/Math/MathML" display="inline" or display="block"
- <mrow> for grouping
- <msub> for subscripts, <msup> for superscripts, <msubsup> for both
- <mtext> ONLY for text subscripts like "error" in P_error: <msub><mi>P</mi><mtext>error</mtext></msub>
- <mi> for identifiers, <mn> for numbers, <mo> for operators
- Unicode entities for special symbols: &#x22C3; (∪), &#x2260; (≠), &#x2026; (…)
- Functions like Pr, error, bigcup must be complete symbols, not character-by-character

Examples of CORRECT MathML:
- P_error(C): <msub><mi>P</mi><mtext>error</mtext></msub><mo>(</mo><mi>C</mi><mo>)</mo>
- Union with limits: <msubsup><mo>&#x22C3;</mo><mrow><mi>i</mi><mo>=</mo><mn>1</mn></mrow><mi>K</mi></msubsup>
- Not equal: <mo>&#x2260;</mo>
- Ellipsis: <mo>&#x2026;</mo>
- Pr: <mi>Pr</mi> (complete, not <mi>P</mi><mi>r</mi>)

VALIDATION CHECKLIST:
✓ No <mtext> for equations (only for text subscripts)
✓ No character-level subscripting of math keywords
✓ Functions treated as complete symbols
✓ Readable by MathJax
✓ Equivalent to original equation

Return as JSON with keys: mathml, latex, confidence"""
        
        return prompt
    
    def _parse_ai_response(
        self,
        content: str,
        log: List[str]
    ) -> Dict:
        """Parse AI response - MUST return valid JSON only.
        
        NON-NEGOTIABLE RULES:
        - All OpenAI outputs MUST be valid JSON
        - No markdown
        - No explanations  
        - No prose
        - Reject any response that cannot be parsed as pure JSON
        """
        try:
            # CRITICAL: Remove any Python code that might be in the response
            # OpenAI sometimes includes code examples - we must NOT execute them
            import re
            
            # CRITICAL: Remove ALL Python code blocks and executable code
            # Remove Python code blocks (```python ... ```)
            content = re.sub(r'```python.*?```', '', content, flags=re.DOTALL | re.IGNORECASE)
            # Remove any code blocks (``` ... ```)
            content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
            
            # Remove any lines that look like Python code (variable assignments, function calls)
            lines = content.split('\n')
            cleaned_lines = []
            for line in lines:
                line_stripped = line.strip()
                # Skip lines that look like Python code (but keep JSON)
                # Pattern: variable assignments (s_1 =, d_1 =, w_1 =, etc.)
                if re.match(r'^\s*[a-z_][a-z0-9_]*\s*=', line_stripped) and not line_stripped.startswith('{'):
                    log.append(f"Skipping Python code line (variable assignment): {line[:50]}")
                    continue
                # Skip import/def/class statements
                if re.match(r'^\s*(import |def |class |from |if |for |while |try |except |return )', line_stripped):
                    log.append(f"Skipping Python code line (statement): {line[:50]}")
                    continue
                # Skip lines with Python-style variable references (s_1, d_1, etc. not in JSON context)
                if re.search(r'\b(s_\d+|d_\d+|w_\d+)\s*=', line_stripped) and not line_stripped.startswith('{'):
                    log.append(f"Skipping Python code line (subscript variable): {line[:50]}")
                    continue
                cleaned_lines.append(line)
            content = '\n'.join(cleaned_lines)
            
            # Additional safety: Remove any remaining Python-like patterns
            # Remove standalone variable assignments outside JSON
            content = re.sub(r'^\s*[a-z_][a-z0-9_]*\s*=\s*[^"{].*$', '', content, flags=re.MULTILINE)
            
            # Try to extract JSON from markdown code blocks
            json_match = None
            for pattern in [
                r'```json\s*(\{.*?\})\s*```',
                r'```\s*(\{.*?\})\s*```',
                r'(\{.*\})'
            ]:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    json_match = match.group(1)
                    break
            
            if json_match:
                # Validate JSON before parsing (ensure it's not executable code)
                json_match_clean = json_match.strip()
                if not json_match_clean.startswith('{'):
                    raise ValueError("JSON match does not start with {")
                
                # Additional safety: Check for Python code patterns in JSON
                if re.search(r'\b(s_\d+|d_\d+|w_\d+)\s*=', json_match_clean):
                    log.append("WARNING: JSON contains Python code patterns, skipping")
                    raise ValueError("JSON contains executable code patterns")
                
                try:
                    result = json.loads(json_match_clean)
                    log.append("Parsed JSON response")
                    return result
                except json.JSONDecodeError as json_err:
                    log.append(f"JSON decode error: {json_err}")
                    raise
            else:
                # Try parsing entire content as JSON
                content_clean = content.strip()
                if not content_clean.startswith('{'):
                    raise ValueError("Content does not start with {")
                
                # Additional safety: Check for Python code patterns
                if re.search(r'\b(s_\d+|d_\d+|w_\d+)\s*=', content_clean):
                    log.append("WARNING: Content contains Python code patterns, skipping")
                    raise ValueError("Content contains executable code patterns")
                
                try:
                    result = json.loads(content_clean)
                    log.append("Parsed JSON response (direct)")
                    return result
                except json.JSONDecodeError as json_err:
                    log.append(f"JSON decode error: {json_err}")
                    raise
                
        except (json.JSONDecodeError, ValueError, AttributeError) as e:
            log.append(f"Failed to parse JSON: {e}")
            log.append("CRITICAL: OpenAI violated JSON-only requirement - response contains markdown/prose")
            logger.warning(f"Could not parse AI response as JSON: {content[:200]}")
            logger.warning("OpenAI response should be JSON-only but contains markdown/explanations")
            
            # REJECT non-JSON responses per MANDATORY RULES
            # Do NOT attempt fallback extraction - this encourages OpenAI to violate JSON-only rule
            raise ValueError(
                f"OpenAI response is not valid JSON (violates JSON-only requirement). "
                f"Response starts with: {content[:100]}"
            )


# Convenience function for easy integration
def convert_with_openai(
    input_text: str,
    input_type: str = "mathml",
    api_key: Optional[str] = None,
    model: str = "gpt-4o-mini"
) -> Dict:
    """
    Convenience function to convert MathML/LaTeX using OpenAI.
    
    Args:
        input_text: Corrupted MathML or LaTeX string
        input_type: "mathml" or "latex"
        api_key: OpenAI API key (or set OPENAI_API_KEY env var)
        model: Model to use
    
    Returns:
        Dict with mathml, latex, confidence, log
    """
    converter = OpenAIMathMLConverter(api_key=api_key, model=model)
    
    if input_type == "mathml":
        return converter.convert_corrupted_mathml(input_text)
    else:
        return converter.convert_latex_to_mathml(input_text)

