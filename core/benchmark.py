import difflib

class MathpixBenchmark:
    def latex_similarity(self, ours, mathpix):
        return difflib.SequenceMatcher(None, ours, mathpix).ratio()

    def mathml_similarity(self, ours, mathpix):
        ours = ours.replace(" ", "")
        mathpix = mathpix.replace(" ", "")
        return difflib.SequenceMatcher(None, ours, mathpix).ratio()

    def evaluate(self, ours_latex, mp_latex, ours_mml, mp_mml):
        return {
            "latex_similarity": round(self.latex_similarity(ours_latex, mp_latex), 3),
            "mathml_similarity": round(self.mathml_similarity(ours_mml, mp_mml), 3),
        }
