"""Screen and camera analysis via OpenRouter vision; no Gemini dependency."""
from core.user_paths import get_user_data_dir
import base64
import io
import json
import sys
from pathlib import Path
import requests
import cv2
import mss
import mss.tools
try:
    import PIL.Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

API_CONFIG_PATH = get_user_data_dir() / "config" / "api_keys.json"
IMG_MAX_W, IMG_MAX_H, JPEG_Q = 640, 360, 55

def _openrouter_key():
    try:
        data = json.loads(API_CONFIG_PATH.read_text(encoding="utf-8"))
        return (data.get("openrouter_api_key") or "").strip()
    except (OSError, ValueError):
        return ""

def _get_camera_index() -> int:
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if "camera_index" in cfg:
            return int(cfg["camera_index"])
    except Exception:
        pass

    print("[Camera] [FIND] No camera index in config. Auto-detecting...")
    best_index = 0

    for idx in range(6):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            continue
        for _ in range(5):
            cap.read()
        ret, frame = cap.read()
        cap.release()
        if ret and frame is not None and frame.mean() > 5:
            best_index = idx
            print(f"[Camera] [OK] Camera found at index {idx} — saving to config.")
            break
        else:
            print(f"[Camera] [WARN]  Index {idx}: no valid frame.")

    try:
        cfg = {}
        if API_CONFIG_PATH.exists():
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["camera_index"] = best_index
        with open(API_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        print(f"[Camera] [SAVE] Camera index {best_index} saved to config.")
    except Exception as e:
        print(f"[Camera] [WARN]  Could not save camera index: {e}")

    return best_index


def _to_jpeg(img_bytes: bytes) -> bytes:
    if not _PIL_OK:
        return img_bytes
    img = PIL.Image.open(io.BytesIO(img_bytes)).convert("RGB")
    resample = getattr(PIL.Image, "Resampling", PIL.Image).BILINEAR
    img.thumbnail([IMG_MAX_W, IMG_MAX_H], resample)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_Q, optimize=False)
    return buf.getvalue()


def _capture_screenshot() -> bytes:
    try:
        if _PIL_OK:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=True).convert("RGB")
            resample = getattr(PIL.Image, "Resampling", PIL.Image).BILINEAR
            img.thumbnail([IMG_MAX_W, IMG_MAX_H], resample)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=JPEG_Q, optimize=False)
            return buf.getvalue()
        else:
            raise RuntimeError("PIL not available")
    except Exception as e:
        print(f"[ScreenProcess] PIL ImageGrab failed ({e}). Falling back to mss.")
        with mss.mss() as sct:
            monitors = getattr(sct, "monitors", []) or []
            if len(monitors) > 1:
                monitor = monitors[1]
            elif monitors:
                monitor = monitors[0]
            else:
                raise RuntimeError("No monitors were detected for screen capture.")
            shot = sct.grab(monitor)
            png_bytes = mss.tools.to_png(shot.rgb, shot.size)
        return _to_jpeg(png_bytes)


def _capture_camera() -> bytes:
    camera_index = _get_camera_index()
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Camera could not be opened: index {camera_index}")
    for _ in range(10):
        cap.read()
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        raise RuntimeError("Could not capture camera frame.")
    if _PIL_OK:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(rgb)
        img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.BILINEAR)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_Q, optimize=False)
        return buf.getvalue()
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_Q])
    return buf.tobytes()



def screen_process(parameters: dict, response: str | None = None, player=None,
                   session_memory=None, image_bytes: bytes | None = None) -> bool:
    params = parameters or {}
    question = (params.get("text") or params.get("user_text") or
                "Describe this image briefly.").strip()
    angle = (params.get("angle") or "screen").lower().strip()
    def fail(message):
        if player and hasattr(player, "update_task_workspace"):
            player.update_task_workspace(status="Vision error", output=message, percent=0)
        if player and hasattr(player, "write_log"):
            player.write_log("Vision: " + message)
        if player and hasattr(player, "set_scanning"):
            player.set_scanning(False, "")
        return False
    api_key = _openrouter_key()
    if not api_key:
        return fail("OpenRouter API key required for screen analysis.")
    if player and hasattr(player, "set_scanning"):
        player.set_scanning(True, "SCANNING SCREEN")
    try:
        if not image_bytes:
            if angle == "camera":
                image_bytes = _capture_camera()
            elif angle in ("active_window", "window") or params.get("target") == "active_window":
                from core.window_context import capture_active_window_screenshot
                image_bytes = capture_active_window_screenshot() or _capture_screenshot()
            else:
                image_bytes = _capture_screenshot()
        image_bytes = _to_jpeg(image_bytes)
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {
                        "url": "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode("ascii")
                    }}
                ]
            }],
            "max_tokens": 600
        }
        reply = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": "Bearer " + api_key,
                     "Content-Type": "application/json"},
            json=payload, timeout=45
        )
        reply.raise_for_status()
        answer = reply.json()["choices"][0]["message"]["content"]
        if isinstance(answer, list):
            answer = " ".join(item.get("text", "") for item in answer
                              if isinstance(item, dict))
        if player and hasattr(player, "write_log"):
            player.write_log("Jarvis (Vision): " + str(answer))
        if player and hasattr(player, "show_content"):
            player.show_content("Screen analysis", str(answer))
        if player and hasattr(player, "update_task_workspace"):
            player.update_task_workspace(status="Completed", output=str(answer), percent=100)
        return True
    except Exception as exc:
        return fail("OpenRouter vision request failed: " + str(exc))
    finally:
        if player and hasattr(player, "set_scanning"):
            player.set_scanning(False, "")

def warmup_session(player=None):
    """OpenRouter vision is request-based; no persistent session to warm up."""
    return None
