import numpy as np

class ConfidenceHeatmap:
    def generate(
        self,
        bbox: dict,
        symbol_boxes: list[dict],
        symbol_confidences: list[float],
        grid=(10, 4),
    ):
        """
        Returns a 2D heatmap normalized to [0,1]
        """
        w, h = bbox["w"], bbox["h"]
        gx, gy = grid
        heatmap = np.zeros((gy, gx))
        counts = np.zeros((gy, gx))

        for box, conf in zip(symbol_boxes, symbol_confidences):
            cx = int((box["x"] / w) * gx)
            cy = int((box["y"] / h) * gy)
            cx = min(gx - 1, max(0, cx))
            cy = min(gy - 1, max(0, cy))

            heatmap[cy][cx] += conf
            counts[cy][cx] += 1

        heatmap = np.divide(
            heatmap, counts, out=np.zeros_like(heatmap), where=counts != 0
        )

        return heatmap.tolist()
