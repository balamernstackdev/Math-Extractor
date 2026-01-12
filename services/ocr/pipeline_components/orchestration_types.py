from typing import TypedDict, List, Optional, Literal

class StrictPipelineResult(TypedDict):
    """Result structure for the StrictMathpixPipeline."""
    source_type: str
    clean_latex: str
    mathml: str
    human_readable: str
    is_valid: bool
    corruption_score: float
    validation_errors: List[str]
    corruption_detected: List[str]
    stage_failed: Optional[str]
    used_ai: bool
    log: List[str]

class PipelineContext(TypedDict):
    """Context object for the pipeline orchestration stages."""
    # Data
    original_input: str
    source_type: Literal["latex", "mathml"]
    clean_latex: str
    mathml: str
    is_valid: bool
    corruption_score: float
    validation_errors: List[str]
    corruption_detected: List[str]
    stage_failed: Optional[str]
    used_ai: bool
    log: List[str]
    
    # State/Flags
    fast_mode: bool
    cache_hit: bool
    
    # Performance
    start_time: float
