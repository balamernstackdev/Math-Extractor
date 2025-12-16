"""Diagnostic tool to identify pipeline failure points."""
from __future__ import annotations

from typing import Dict, List, Tuple
from core.logger import logger


class PipelineDiagnostic:
    """Diagnose where the OCR → MathML pipeline is failing."""
    
    def __init__(self):
        self.diagnosis_results = []
    
    def diagnose_pipeline(self, 
                         raw_ocr: str,
                         reconstructed_latex: str,
                         final_mathml: str,
                         expected_equation: str = "") -> Dict:
        """
        Diagnose pipeline issues at each stage.
        
        Args:
            raw_ocr: Raw OCR output from Tesseract
            reconstructed_latex: LaTeX after reconstruction
            final_mathml: Final MathML output
            expected_equation: Expected equation (if known)
        
        Returns:
            Dictionary with diagnosis results
        """
        diagnosis = {
            'stage': 'unknown',
            'issues': [],
            'severity': 'low',
            'recommendations': []
        }
        
        # Stage 1: OCR Quality Check
        ocr_issues = self._check_ocr_quality(raw_ocr, expected_equation)
        if ocr_issues['severity'] == 'critical':
            diagnosis.update({
                'stage': 'ocr',
                'issues': ocr_issues['issues'],
                'severity': 'critical',
                'recommendations': ocr_issues['recommendations']
            })
            return diagnosis
        
        # Stage 2: Reconstruction Check
        recon_issues = self._check_reconstruction(raw_ocr, reconstructed_latex, expected_equation)
        if recon_issues['severity'] in ['high', 'critical']:
            diagnosis.update({
                'stage': 'reconstruction',
                'issues': recon_issues['issues'],
                'severity': recon_issues['severity'],
                'recommendations': recon_issues['recommendations']
            })
            return diagnosis
        
        # Stage 3: MathML Conversion Check
        mathml_issues = self._check_mathml_conversion(reconstructed_latex, final_mathml, expected_equation)
        if mathml_issues['severity'] in ['high', 'critical']:
            diagnosis.update({
                'stage': 'mathml_conversion',
                'issues': mathml_issues['issues'],
                'severity': mathml_issues['severity'],
                'recommendations': mathml_issues['recommendations']
            })
            return diagnosis
        
        # All stages passed
        diagnosis.update({
            'stage': 'success',
            'severity': 'low',
            'recommendations': ['Pipeline working correctly']
        })
        
        return diagnosis
    
    def _check_ocr_quality(self, raw_ocr: str, expected: str = "") -> Dict:
        """Check OCR output quality."""
        issues = []
        recommendations = []
        severity = 'low'
        
        if not raw_ocr or len(raw_ocr.strip()) < 3:
            issues.append("OCR returned empty or very short output")
            severity = 'critical'
            recommendations.append("Check image quality and Tesseract installation")
            return {'issues': issues, 'severity': severity, 'recommendations': recommendations}
        
        # Check for common OCR failures with math symbols
        math_symbols_missing = []
        if 'Σ' in expected or 'sum' in expected.lower():
            if 'Σ' not in raw_ocr and 'sum' not in raw_ocr.lower() and '\\sum' not in raw_ocr:
                math_symbols_missing.append('Σ (sigma/sum)')
                severity = 'critical'
        
        if 'max' in expected.lower():
            if 'max' not in raw_ocr.lower() and '\\max' not in raw_ocr:
                math_symbols_missing.append('max')
                severity = 'critical'
        
        if math_symbols_missing:
            issues.append(f"Critical math symbols missing from OCR: {', '.join(math_symbols_missing)}")
            recommendations.append("Tesseract OCR is not suitable for mathematical formulas")
            recommendations.append("Use math-specific OCR: pix2tex, MathPix API, or TrOCR fine-tuned on math")
        
        # Check for character corruption
        suspicious_patterns = [
            (r'[X-Z]_[x-z]', 'Suspicious capital letter subscripts (likely OCR corruption)'),
            (r'[A-Z]{2,}_[a-z]', 'Multiple capital letters in subscripts (likely OCR error)'),
        ]
        
        import re
        for pattern, description in suspicious_patterns:
            if re.search(pattern, raw_ocr):
                issues.append(description)
                if severity != 'critical':
                    severity = 'high'
        
        # Check if OCR output looks like gibberish
        if len(raw_ocr) > 10:
            uppercase_ratio = sum(1 for c in raw_ocr if c.isupper()) / len(raw_ocr)
            if uppercase_ratio > 0.6 and not any(c in raw_ocr for c in "=+-*/()[]{}"):
                issues.append("OCR output appears to be gibberish (high uppercase ratio, no operators)")
                severity = 'critical'
                recommendations.append("Image may be corrupted or Tesseract misconfigured")
        
        return {'issues': issues, 'severity': severity, 'recommendations': recommendations}
    
    def _check_reconstruction(self, raw_ocr: str, reconstructed: str, expected: str = "") -> Dict:
        """Check if reconstruction improved the output."""
        issues = []
        recommendations = []
        severity = 'low'
        
        if not reconstructed or len(reconstructed.strip()) < len(raw_ocr.strip()) * 0.5:
            issues.append("Reconstruction produced significantly shorter output (may have lost content)")
            severity = 'high'
            recommendations.append("Review reconstruction patterns - may be too aggressive")
        
        # Check if critical symbols are still missing after reconstruction
        if 'Σ' in expected or 'sum' in expected.lower():
            if '\\sum' not in reconstructed and 'sum' not in reconstructed.lower():
                issues.append("Summation symbol still missing after reconstruction")
                severity = 'critical'
                recommendations.append("Reconstruction cannot fix severe OCR corruption")
                recommendations.append("Need better OCR model (pix2tex, MathPix)")
        
        if 'max' in expected.lower():
            if '\\max' not in reconstructed and 'max' not in reconstructed.lower():
                issues.append("max operator still missing after reconstruction")
                severity = 'critical'
        
        return {'issues': issues, 'severity': severity, 'recommendations': recommendations}
    
    def _check_mathml_conversion(self, latex: str, mathml: str, expected: str = "") -> Dict:
        """Check MathML conversion quality."""
        issues = []
        recommendations = []
        severity = 'low'
        
        if not mathml or '<math' not in mathml:
            issues.append("MathML conversion failed - no <math> element")
            severity = 'critical'
            return {'issues': issues, 'severity': severity, 'recommendations': recommendations}
        
        # Check for corruption patterns we identified earlier
        corruption_patterns = [
            (r'<mo stretchy="false">\]</mo>', 'Missing opening bracket in MathML'),
            (r'<mi>[D-Z]</mi>.*?<msub>.*?<mi>[O-Z]</mi>', 'Suspicious capital letter subscripts in MathML'),
        ]
        
        import re
        for pattern, description in corruption_patterns:
            if re.search(pattern, mathml):
                issues.append(description)
                severity = 'high'
                recommendations.append("MathML corruption detected - likely from corrupted LaTeX input")
        
        # Check if expected symbols are in MathML
        if '\\sum' in latex or 'sum' in latex.lower():
            if '∑' not in mathml and 'sum' not in mathml.lower():
                issues.append("Summation missing from MathML despite being in LaTeX")
                severity = 'high'
        
        return {'issues': issues, 'severity': severity, 'recommendations': recommendations}
    
    def generate_report(self, diagnosis: Dict) -> str:
        """Generate a human-readable diagnostic report."""
        report = []
        report.append("=" * 60)
        report.append("PIPELINE DIAGNOSTIC REPORT")
        report.append("=" * 60)
        report.append(f"\nFailure Stage: {diagnosis['stage'].upper()}")
        report.append(f"Severity: {diagnosis['severity'].upper()}")
        
        if diagnosis['issues']:
            report.append(f"\nIssues Found ({len(diagnosis['issues'])}):")
            for i, issue in enumerate(diagnosis['issues'], 1):
                report.append(f"  {i}. {issue}")
        
        if diagnosis['recommendations']:
            report.append(f"\nRecommendations ({len(diagnosis['recommendations'])}):")
            for i, rec in enumerate(diagnosis['recommendations'], 1):
                report.append(f"  {i}. {rec}")
        
        report.append("\n" + "=" * 60)
        return "\n".join(report)

