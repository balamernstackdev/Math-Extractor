"""
Example: Using OpenAI API for MathML/Equation Conversion

This example shows how to use OpenAI API to convert corrupted MathML
or LaTeX to clean formats as a fallback or enhancement.

Setup:
1. Install openai package: pip install openai
2. Set your API key: export OPENAI_API_KEY="your-key-here"
   Or pass it directly to the converter
"""

import os
from services.ocr.openai_mathml_converter import OpenAIMathMLConverter, convert_with_openai

# Example 1: Direct usage
def example_direct_usage():
    """Example using OpenAIMathMLConverter directly."""
    print("=" * 80)
    print("Example 1: Direct OpenAI Converter Usage")
    print("=" * 80)
    
    # Initialize converter (uses OPENAI_API_KEY env var if not provided)
    converter = OpenAIMathMLConverter(
        api_key=os.getenv("OPENAI_API_KEY"),  # Or pass directly
        model="gpt-4o-mini"  # or "gpt-4o", "gpt-3.5-turbo", etc.
    )
    
    # Example corrupted MathML
    corrupted_mathml = """<math xmlns="http://www.w3.org/1998/Math/MathML">
        <mrow>
            <msub><mi>\\m</mi><mrow><mi>a</mi></mrow></msub>
            <msub><mi>t</mi><mrow><mi>h</mi></mrow></msub>
            <msub><mi>b</mi><mrow><mi>f</mi></mrow></msub>
            <mi>D</mi>
            <mo>=</mo>
            <mo>{</mo>
            <mrow>
                <mo>(</mo>
                <msub><mi>D</mi><mn>1</mn></msub>
                <mo>,</mo>
                <mo>...</mo>
                <mo>,</mo>
                <msub><mi>D</mi><mi>K</mi></msub>
                <mo>)</mo>
                <mo>∈</mo>
                <msup><mi>R</mi><mrow><mo>+</mo></mrow></msup>
            </mrow>
            <mo>}</mo>
        </mrow>
    </math>"""
    
    # Convert corrupted MathML
    result = converter.convert_corrupted_mathml(
        corrupted_mathml,
        target_format="mathml",
        include_latex=True
    )
    
    print(f"\nInput (corrupted): {corrupted_mathml[:100]}...")
    print(f"\nOutput MathML: {result['mathml'][:200]}...")
    print(f"\nOutput LaTeX: {result['latex']}")
    print(f"\nConfidence: {result['confidence']:.3f}")
    print(f"\nLog entries: {len(result['log'])}")


# Example 2: Convenience function
def example_convenience_function():
    """Example using the convenience function."""
    print("\n" + "=" * 80)
    print("Example 2: Convenience Function")
    print("=" * 80)
    
    # Convert LaTeX to MathML
    latex = r"D = \{(D_1, \ldots, D_K) \in \mathbb{R}_+^K : \forall w_1, \ldots, w_K \in \mathbb{R}_+\}"
    
    result = convert_with_openai(
        latex,
        input_type="latex",
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4o-mini"
    )
    
    print(f"\nInput LaTeX: {latex}")
    print(f"\nOutput MathML: {result['mathml'][:200]}...")
    print(f"\nConfidence: {result['confidence']:.3f}")


# Example 3: Integration with recovery pipeline
def example_pipeline_integration():
    """Example showing integration with the recovery pipeline."""
    print("\n" + "=" * 80)
    print("Example 3: Integration with Recovery Pipeline")
    print("=" * 80)
    
    from services.ocr.mathml_recovery_pro import ultra_mathml_recover
    
    corrupted_mathml = """<math xmlns="http://www.w3.org/1998/Math/MathML">
        <mrow>
            <msub><mi>\\m</mi><mrow><mi>a</mi></mrow></msub>
            <msub><mi>t</mi><mrow><mi>h</mi></mrow></msub>
            <msub><mi>b</mi><mrow><mi>f</mi></mrow></msub>
            <mi>D</mi>
        </mrow>
    </math>"""
    
    # Use rule-based recovery first, with OpenAI fallback
    result = ultra_mathml_recover(
        corrupted_mathml,
        force_mode=True,
        use_openai_fallback=True,  # Enable OpenAI fallback
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_model="gpt-4o-mini"
    )
    
    print(f"\nRecovery Result:")
    print(f"  LaTeX: {result['latex']}")
    print(f"  Confidence: {result['confidence']:.3f}")
    print(f"  Used OpenAI: {'OpenAI' in str(result.get('log', []))}")


if __name__ == "__main__":
    # Check if API key is set
    if not os.getenv("OPENAI_API_KEY"):
        print("WARNING: OPENAI_API_KEY environment variable not set!")
        print("Set it with: export OPENAI_API_KEY='your-key-here'")
        print("\nContinuing with examples (will fail if API key not provided)...\n")
    
    try:
        example_direct_usage()
        example_convenience_function()
        example_pipeline_integration()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you have:")
        print("1. Installed openai: pip install openai")
        print("2. Set OPENAI_API_KEY environment variable")
        print("3. Have valid API credits")

