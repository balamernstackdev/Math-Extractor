"""
OpenAI-powered LaTeX to MathML converter.

This module provides AI-powered conversion as a fallback when
traditional latex2mathml fails on complex multiline equations.
"""

import os
import re
import logging
from typing import Optional
try:
    from openai import OpenAI
    import httpx
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    httpx = None

logger = logging.getLogger(__name__)


class OpenAIMathMLConverter:
    """
    Convert LaTeX to MathML using OpenAI GPT-4.
    
    This is used as a fallback for complex multiline equations that
    latex2mathml cannot handle properly.
    """
    
    def __init__(self, model: str = "gpt-4o-mini", api_key: Optional[str] = None):
        """
        Initialize the OpenAI converter.
        
        Args:
            model: OpenAI model to use (default: gpt-4o-mini for cost efficiency)
            api_key: Optional API key. If not provided, reads form os.environ.
        """
        self.model = model
        
        # Get API key from argument or environment
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        # Fallback to settings if available (Streamlit Cloud Secrets)
        if not self.api_key:
            try:
                from core.config import settings
                self.api_key = settings.openai_api_key
            except ImportError:
                pass
                
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables or settings")
        
        # --- ROBUST PROXY HANDLING ---
        self._http_client = None
        if httpx:
            class SafeHttpxClient(httpx.Client):
                def __init__(self, *args, **kwargs):
                    if 'proxies' in kwargs:
                        kwargs.pop('proxies')
                    super().__init__(*args, **kwargs)
            self._http_client = SafeHttpxClient()

        # Initialize client
        client_kwargs = {"api_key": self.api_key}
        if self._http_client:
            client_kwargs["http_client"] = self._http_client
            
        self.client = OpenAI(**client_kwargs)
        logger.info(f"OpenAI MathML converter initialized (model: {model})")
    
    def latex_to_mathml(self, latex: str) -> str:
        """
        Convert LaTeX to MathML using GPT-4.
        
        Args:
            latex: LaTeX equation string
            
        Returns:
            MathML string
            
        Raises:
            ValueError: If conversion fails or returns invalid MathML
        """
        if not latex or not latex.strip():
            raise ValueError("Empty LaTeX input")
        
        # Create the prompt
        prompt = self._create_prompt(latex)
        
        try:
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a mathematical notation expert. Convert LaTeX equations to valid Presentation MathML. \nRULES:\n1. Output ONLY the MathML code (starts with <math>).\n2. For multiline equations (align, split, gather), use <mtable> structure.\n3. Preserve vertical alignment and line breaks.\n4. Ensure ALL operators and symbols are correctly escaped.\n5. Do NOT include markdown formatting or explanations."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,  # Deterministic output
                max_tokens=2000
            )
            
            # Extract MathML from response
            mathml = response.choices[0].message.content.strip()
            
            # Clean up response (remove markdown code blocks if present)
            mathml = self._clean_response(mathml)
            
            # Validate output
            if not mathml or '<math' not in mathml:
                raise ValueError("Invalid MathML returned by OpenAI")
            
            logger.info("Successfully converted LaTeX to MathML using OpenAI (length: %d)", len(mathml))
            return mathml
            
        except Exception as e:
            logger.error("OpenAI API call failed: %s", e)
            raise ValueError(f"OpenAI MathML conversion failed: {e}")

    def convert_image_to_latex(self, image, table_mode: bool = False, handwriting_mode: bool = False) -> str:
        """
        Convert an image of an equation to LaTeX using GPT-4o Vision.
        Args:
            image: PIL Image object
            table_mode: If True, optimized for table extraction
            handwriting_mode: If True, optimized for handwriting
        Returns:
            Clean LaTeX string
        """
        import base64
        import io
        
        # Determine model - use gpt-4o for vision
        vision_model = "gpt-4o"
        
        try:
            # Convert PIL image to base64
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            logger.info(f"Sending image to OpenAI Vision ({vision_model})... Mode: Table={table_mode}, Handwriting={handwriting_mode}")
            
            system_prompt = "You are a mathematical OCR expert. Extract the equation from the image and output ONLY the corresponding LaTeX code. Do not output MathML. Do not wrap in markdown blocks like ```latex ... ```. Output raw LaTeX only."
            
            if table_mode:
                system_prompt = (
                    "You are a mathematical and table OCR expert. Extract the table from the image and output ONLY the corresponding LaTeX 'tabular' code. "
                    "Ensure you preserve the grid structure, alignment, and cell contents exactly. "
                    "Use standard environments like \\begin{tabular} or \\begin{array}. "
                    "Do not output markdown or explanations."
                )
            elif handwriting_mode:
                 system_prompt = (
                    "You are a mathematical OCR expert specialized in handwriting. Extract the handwritten equation from the image and output ONLY the corresponding LaTeX code. "
                    "Be meticulous with messy characters. Do not output markdown or explanations."
                )

            user_text = "Extract this equation to LaTeX:"
            if table_mode:
                user_text = "Extract this table to LaTeX tabular code:"
            elif handwriting_mode:
                user_text = "Extract this handwritten equation to LaTeX:"

            response = self.client.chat.completions.create(
                model=vision_model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2000
            )
            
            latex = response.choices[0].message.content.strip()
            
            # Clean up response
            latex = re.sub(r'```(?:latex|tex)?\n?', '', latex)
            latex = re.sub(r'```\n?', '', latex)
            
            logger.info("OpenAI Vision result: %s", latex[:100])
            return latex
            
        except Exception as e:
            logger.error("OpenAI Vision API call failed: %s", e)
            return ""
    
    def _create_prompt(self, latex: str) -> str:
        """Create the prompt for OpenAI."""
        return f"""Convert the following LaTeX equation to valid MathML (Presentation MathML).

Requirements:
1. Use proper MathML structure with <math xmlns="http://www.w3.org/1998/Math/MathML" display="block">
2. CRITICAL: For multiline equations (align, split, gather), you MUST use <mtable> with correct <mtr> and <mtd> structure.
3. Preserve vertical alignment where '&' is used in LaTeX.
4. Use <munder> and <mover> for large operators like ∑, lim, sup
5. Use proper operator tags: <mo> for =, +, -, ×, etc.
6. Use <msub>, <msup>, <msubsup> for subscripts/superscripts
7. Use <mfrac> for fractions
8. NEVER put LaTeX commands in <mtext> tags
9. Ensure all braces {{ }} are properly converted to <mo>{{</mo> and <mo>}}</mo>

LaTeX:
{latex}

Output only the MathML code (no explanations):"""
    
    def _clean_response(self, response: str) -> str:
        """
        Clean up the OpenAI response.
        
        Removes markdown code blocks and extra whitespace.
        """
        # Remove markdown code blocks
        response = re.sub(r'```(?:xml|mathml)?\n?', '', response)
        response = re.sub(r'```\n?', '', response)
        
        # Remove any leading/trailing text before <math> tag
        math_start = response.find('<math')
        if math_start > 0:
            response = response[math_start:]
       
        math_end = response.rfind('</math>')
        if math_end > 0:
            response = response[:math_end + 7]  # +7 for "</math>"
        
        return response.strip()
