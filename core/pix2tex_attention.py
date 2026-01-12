import numpy as np

class AttentionBoxExtractor:
    def extract(
        self,
        attention_maps: list[np.ndarray],
        image_shape: tuple[int, int],
        tokens: list[str],
        threshold=0.6,
    ):
        """
        attention_maps: list of (H, W) attention maps per token
        image_shape: (height, width)
        tokens: decoded LaTeX tokens
        """
        H, W = image_shape
        boxes = []

        for token, attn in zip(tokens, attention_maps):
            attn = attn / attn.max()
            mask = attn > threshold

            if not mask.any():
                continue

            ys, xs = np.where(mask)
            x_min, x_max = xs.min(), xs.max()
            y_min, y_max = ys.min(), ys.max()

            boxes.append({
                "symbol": token,
                "x": int(x_min / attn.shape[1] * W),
                "y": int(y_min / attn.shape[0] * H),
                "w": int((x_max - x_min) / attn.shape[1] * W),
                "h": int((y_max - y_min) / attn.shape[0] * H),
            })

        return boxes
