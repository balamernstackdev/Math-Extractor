from core.semantic_reconstruction import SemanticReconstructor

reconstructor = SemanticReconstructor()

# STEP 2.5 — semantic reconstruction
if reconstructor.detect_truncation(latex):
    recovered = reconstructor.reconstruct(latex)
    if recovered:
        logger.info("Applied semantic multiline reconstruction")
        latex = recovered
