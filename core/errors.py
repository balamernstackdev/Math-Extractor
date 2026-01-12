"""
Structured Error Model for Math Extraction Pipeline

Implements zero-tolerance error reporting with severity classification,
error codes, and suggested fixes.

Author: AI Systems Engineering Team
Date: 2025-12-18
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any


class ValidationSeverity(Enum):
    """Error severity levels for pipeline validation."""
    WARNING = 1   # Log only, continue processing
    ERROR = 2     # Attempt recovery (AI repair), then continue
    BLOCKER = 3   # STOP pipeline immediately, reject equation
    

class PipelineStage(Enum):
    """Pipeline stages where errors can occur."""
    OCR = "ocr"
    LATEX_VALIDATE = "latex_validate"
    CONVERT = "convert"
    MATHML_VALIDATE = "mathml_validate"
    GATEKEEPER = "gatekeeper"


@dataclass
class PipelineError:
    """
    Structured error representation with full context.
    
    Attributes:
        code: Unique error code (format: STAGE_COMPONENT_SEVERITY_NUMBER)
        stage: Pipeline stage where error occurred
        severity: Error severity level
        message: Human-readable error description
        context: Additional error context (LaTeX snippet, line numbers, etc.)
        suggested_fix: Optional suggestion for how to fix the error
        timestamp: When the error occurred
        equation_id: Optional link to specific equation in database
    """
    code: str
    stage: PipelineStage
    severity: ValidationSeverity
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    suggested_fix: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    equation_id: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "code": self.code,
            "stage": self.stage.value,
            "severity": self.severity.name,
            "message": self.message,
            "context": self.context,
            "suggested_fix": self.suggested_fix,
            "timestamp": self.timestamp.isoformat(),
            "equation_id": self.equation_id
        }
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        severity_emoji = {
            ValidationSeverity.WARNING: "⚠️",
            ValidationSeverity.ERROR: "❌",
            ValidationSeverity.BLOCKER: "🛑"
        }
        emoji = severity_emoji.get(self.severity, "❓")
        
        base = f"{emoji} [{self.code}] {self.severity.name}: {self.message}"
        if self.suggested_fix:
            base += f"\n   💡 Fix: {self.suggested_fix}"
        return base


@dataclass
class ValidationError(PipelineError):
    """Specialized error for validation failures."""
    rule_id: str = ""  # e.g., "MATHML_R02" for rule #2
    
    def __post_init__(self):
        """Set code based on rule_id if not provided."""
        if not self.code and self.rule_id:
            severity_code = self.severity.name[0]  # W, E, or B
            self.code = f"{self.stage.value.upper()}_{self.rule_id}_{severity_code}"


@dataclass
class PipelineResult:
    """
    Complete result of pipeline processing with metrics and errors.
    
    Attributes:
        success: Whether processing succeeded
        output: Final MathML output (if success=True)
        errors: List of errors encountered (severity: ERROR or BLOCKER)
        warnings: List of warnings encountered (severity: WARNING)
        validation_passed: Whether validation passed all rules
        ai_repair_used: Whether AI was used to repair corrupted LaTeX
        total_time_ms: Total processing time in milliseconds
        metrics: Additional processing metrics
    """
    success: bool
    output: Optional[str] = None
    errors: List[PipelineError] = field(default_factory=list)
    warnings: List[PipelineError] = field(default_factory=list)
    
    # Validation status
    validation_passed: bool = False
    
    # Processing metadata
    ai_repair_used: bool = False
    total_time_ms: int = 0
    
    # Additional metrics
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def add_error(self, error: PipelineError):
        """Add an error to the appropriate list based on severity."""
        if error.severity == ValidationSeverity.WARNING:
            self.warnings.append(error)
        else:
            self.errors.append(error)
            if error.severity == ValidationSeverity.BLOCKER:
                self.success = False
    
    def has_blockers(self) -> bool:
        """Check if any BLOCKER errors exist."""
        return any(e.severity == ValidationSeverity.BLOCKER for e in self.errors)
    
    def get_primary_error(self) -> Optional[PipelineError]:
        """Get the first BLOCKER or ERROR (for UI display)."""
        # Prioritize BLOCKERs
        blockers = [e for e in self.errors if e.severity == ValidationSeverity.BLOCKER]
        if blockers:
            return blockers[0]
        
        # Then ERRORs
        errors = [e for e in self.errors if e.severity == ValidationSeverity.ERROR]
        if errors:
            return errors[0]
        
        return None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "output": self.output,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "validation_passed": self.validation_passed,
            "ai_repair_used": self.ai_repair_used,
            "total_time_ms": self.total_time_ms,
            "metrics": self.metrics
        }
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        if self.success:
            status = "✅ SUCCESS"
        elif self.has_blockers():
            status = "🛑 BLOCKED"
        else:
            status = "❌ FAILED"
        
        lines = [
            f"{status}",
            f"Errors: {len(self.errors)} | Warnings: {len(self.warnings)}",
            f"Validation: {'PASS' if self.validation_passed else 'FAIL'}",
            f"AI Repair: {'YES' if self.ai_repair_used else 'NO'}",
            f"Time: {self.total_time_ms}ms"
        ]
        
        if self.errors:
            lines.append("\nErrors:")
            for error in self.errors[:3]:  # Show first 3 errors
                lines.append(f"  - {error}")
            if len(self.errors) > 3:
                lines.append(f"  ... and {len(self.errors) - 3} more")
        
        return "\n".join(lines)


# ============================================================================
# ERROR CODE REGISTRY
# ============================================================================

class ErrorCodes:
    """Registry of all error codes used in the pipeline."""
    
    # OCR Errors
    OCR_PIX2TEX_E001 = "OCR_PIX2TEX_E001"  # pix2tex model error
    OCR_PIX2TEX_E002 = "OCR_PIX2TEX_E002"  # Image preprocessing failed
    OCR_EMPTY_B001 = "OCR_EMPTY_B001"      # No text extracted (BLOCKER)
    
    # LaTeX Validation Errors
    LATEX_BRACES_B001 = "LATEX_BRACES_B001"            # Unbalanced braces (BLOCKER)
    LATEX_TRUNCATE_B002 = "LATEX_TRUNCATE_B002"        # Truncated command (BLOCKER)
    LATEX_DELIMITERS_E001 = "LATEX_DELIMITERS_E001"    # Unbalanced \left \right (ERROR)
    LATEX_ENVIRONMENTS_B003 = "LATEX_ENVIRONMENTS_B003" # Unbalanced \begin \end (BLOCKER)
    LATEX_ENV_MISMATCH_B004 = "LATEX_ENV_MISMATCH_B004" # Environment name mismatch (BLOCKER)
    LATEX_INVALID_CHAR_B005 = "LATEX_INVALID_CHAR_B005" # Control characters (BLOCKER)
    LATEX_FRACTION_W001 = "LATEX_FRACTION_W001"         # Empty fraction (WARNING)
    LATEX_PARENS_E002 = "LATEX_PARENS_E002"             # Unbalanced parentheses (ERROR)
    LATEX_BRACKETS_E003 = "LATEX_BRACKETS_E003"         # Unbalanced brackets (ERROR)
    
    # Conversion Errors
    CONV_LATEX2MATHML_E001 = "CONV_LATEX2MATHML_E001"  # Conversion exception
    CONV_EMPTY_OUTPUT_B001 = "CONV_EMPTY_OUTPUT_B001"   # Empty MathML output (BLOCKER)
    
    # MathML Validation Errors (BLOCKER rules)
    MATHML_OPERATOR_MI_B001 = "MATHML_OPERATOR_MI_B001"          # Operator in <mi> tag
    MATHML_NAMESPACE_B002 = "MATHML_NAMESPACE_B002"              # Missing namespace
    MATHML_ROOT_B003 = "MATHML_ROOT_B003"                        # Invalid root element
    MATHML_SUMMATION_STRUCT_B004 = "MATHML_SUMMATION_STRUCT_B004" # Summation structure
    
    # MathML Validation Errors (ERROR rules)
    MATHML_FENCES_E001 = "MATHML_FENCES_E001"         # Unbalanced fences
    MATHML_ASCII_MATH_E002 = "MATHML_ASCII_MATH_E002" # ASCII math symbols
    MATHML_EMPTY_ELEM_E003 = "MATHML_EMPTY_ELEM_E003" # Empty elements
    MATHML_TAGS_E004 = "MATHML_TAGS_E004"             # Unbalanced tags
    
    # MathML Validation Errors (WARNING rules)
    MATHML_DISPLAY_W001 = "MATHML_DISPLAY_W001"       # Display attribute
    MATHML_ENTITY_W002 = "MATHML_ENTITY_W002"         # Malformed entity
    
    # Gatekeeper Errors (all BLOCKER)
    GATE_LLM_GENERATED_B001 = "GATE_LLM_GENERATED_B001" # LLM-generated MathML
    GATE_LATEX_IN_MTEXT_B002 = "GATE_LATEX_IN_MTEXT_B002" # LaTeX in <mtext>
    GATE_JS_ERROR_B003 = "GATE_JS_ERROR_B003"           # JavaScript error pattern
    GATE_ARRAY_IN_MTEXT_B004 = "GATE_ARRAY_IN_MTEXT_B004" # Array in <mtext>
    GATE_TOKEN_SHREDDING_B005 = "GATE_TOKEN_SHREDDING_B005" # Token shredding detected
    
    # Multiline MathML Errors (Phase 3)
    MULTILINE_NO_ROWS_E001 = "MULTILINE_NO_ROWS_E001"         # <mtable> has no rows
    MULTILINE_NO_CELLS_E002 = "MULTILINE_NO_CELLS_E002"       # <mtr> has no cells
    MULTILINE_EMPTY_ROW_W001 = "MULTILINE_EMPTY_ROW_W001"     # Completely empty row
    MULTILINE_COL_MISMATCH_W002 = "MULTILINE_COL_MISMATCH_W002" # Inconsistent column count
    MULTILINE_INVALID_ALIGN_E003 = "MULTILINE_INVALID_ALIGN_E003" # Invalid columnalign value
    MULTILINE_INVALID_NESTING_E004 = "MULTILINE_INVALID_NESTING_E004" # Invalid table nesting
    MULTILINE_MALFORMED_TABLE_B001 = "MULTILINE_MALFORMED_TABLE_B001" # Malformed <mtable> structure


def create_error(
    code: str,
    stage: PipelineStage,
    severity: ValidationSeverity,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    suggested_fix: Optional[str] = None
) -> PipelineError:
    """
    Factory function to create a structured error.
    
    Example:
        error = create_error(
            code=ErrorCodes.MATHML_OPERATOR_MI_B001,
            stage=PipelineStage.MATHML_VALIDATE,
            severity=ValidationSeverity.BLOCKER,
            message="Operator '=' found in <mi> tag instead of <mo>",
            context={"latex": "x = 1", "position": 5},
            suggested_fix="Change <mi>=</mi> to <mo>=</mo>"
        )
    """
    return PipelineError(
        code=code,
        stage=stage,
        severity=severity,
        message=message,
        context=context or {},
        suggested_fix=suggested_fix
    )
