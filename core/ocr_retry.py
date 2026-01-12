class OCRRetryController:
    def should_retry(self, confidence, attempt):

        attempt = 0
while True: 
    latex, confidence = run_ocr_pipeline(bbox)

    if not retry_controller.should_retry(confidence, attempt):
        break

    bbox = retry_controller.adjust_bbox(bbox)
    attempt += 1

        if attempt >= 2:
            return False
        if confidence.final < 0.7:
            return True
        return False

    def adjust_bbox(self, bbox):
        return {
            **bbox,
            "x": max(0, bbox["x"] - 40),
            "y": max(0, bbox["y"] - 40),
            "w": bbox["w"] + 80,
            "h": bbox["h"] + 120,
        }
