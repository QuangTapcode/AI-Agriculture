"""Render the throwaway UI prototype to an MP4 through Chrome DevTools."""

import argparse
import base64
import json
import time
from urllib.request import urlopen

import cv2
import numpy as np
import websocket


class DevTools:
    def __init__(self, websocket_url: str):
        self.socket = websocket.create_connection(websocket_url, timeout=15)
        self.message_id = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self.message_id += 1
        current_id = self.message_id
        self.socket.send(json.dumps({"id": current_id, "method": method, "params": params or {}}))
        while True:
            payload = json.loads(self.socket.recv())
            if payload.get("id") == current_id:
                if "error" in payload:
                    raise RuntimeError(payload["error"])
                return payload.get("result", {})


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1 - (1 - value) ** 3


def scroll_position(second: float) -> float:
    if second < 1.8:
        return 0
    if second < 4.7:
        return 820 * ease((second - 1.8) / 2.9)
    if second < 5.6:
        return 820
    if second < 8.7:
        return 820 + 1000 * ease((second - 5.6) / 3.1)
    return 1820


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-port", type=int, default=9223)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seconds", type=float, default=10.5)
    parser.add_argument("--fps", type=int, default=20)
    args = parser.parse_args()

    targets = json.load(urlopen(f"http://127.0.0.1:{args.debug_port}/json", timeout=10))
    page = next(item for item in targets if item.get("type") == "page")
    devtools = DevTools(page["webSocketDebuggerUrl"])
    devtools.call("Page.enable")
    devtools.call("Runtime.enable")
    devtools.call("Emulation.setDeviceMetricsOverride", {
        "width": 1440,
        "height": 900,
        "deviceScaleFactor": 1,
        "mobile": False,
    })
    devtools.call("Runtime.evaluate", {
        "expression": "document.fonts.ready.then(() => window.scrollTo(0, 0))",
        "awaitPromise": True,
    })
    time.sleep(1.2)

    writer = cv2.VideoWriter(
        args.output,
        cv2.VideoWriter_fourcc(*"mp4v"),
        args.fps,
        (1440, 900),
    )
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not create the MP4 file")

    frame_count = round(args.seconds * args.fps)
    for frame_index in range(frame_count):
        second = frame_index / args.fps
        y = scroll_position(second)
        mouse_x = 1030 + np.sin(second * 1.3) * 170
        mouse_y = 420 + np.cos(second * 1.1) * 100
        devtools.call("Runtime.evaluate", {"expression": f"window.scrollTo(0, {y:.2f})"})
        devtools.call("Input.dispatchMouseEvent", {
            "type": "mouseMoved",
            "x": float(mouse_x),
            "y": float(mouse_y),
        })
        captured = devtools.call("Page.captureScreenshot", {
            "format": "jpeg",
            "quality": 90,
            "fromSurface": True,
        })
        encoded = np.frombuffer(base64.b64decode(captured["data"]), dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
        if image.shape[1::-1] != (1440, 900):
            image = cv2.resize(image, (1440, 900), interpolation=cv2.INTER_AREA)
        writer.write(image)

    writer.release()
    print(f"Rendered {frame_count} frames to {args.output}")


if __name__ == "__main__":
    main()
