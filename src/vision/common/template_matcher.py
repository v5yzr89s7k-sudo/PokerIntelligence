from pathlib import Path
import cv2


def match_template(image_path: Path, template_path: Path):
    image = cv2.imread(str(image_path))
    template = cv2.imread(str(template_path))

    if image is None:
        raise FileNotFoundError(f"Could not read image: {image_path}")
    if template is None:
        raise FileNotFoundError(f"Could not read template: {template_path}")

    result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    h, w = template.shape[:2]
    return {
        "confidence": float(max_val),
        "x": int(max_loc[0]),
        "y": int(max_loc[1]),
        "w": int(w),
        "h": int(h),
    }
