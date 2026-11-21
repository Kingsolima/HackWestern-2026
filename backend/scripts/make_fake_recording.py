"""Write the fetch recording the fake swap worker's VERIFY stage replays.

Run from backend/: uv run python -m scripts.make_fake_recording
"""

import asyncio

from app.config import settings
from app.orchestrator.job import VERIFY_PASSES
from app.orchestrator.workers import FAKE_HTML, FAKE_URL
from app.tfclient.recorder import Recorder


async def main() -> None:
    recorder = Recorder(settings.recordings_dir, "live")

    async def fake_response() -> dict:
        result = {"url": FAKE_URL, "final_url": FAKE_URL, "format": "html", "text": FAKE_HTML}
        return {"results": [result], "errors": [], "fake": True}

    for selectors in VERIFY_PASSES:
        request = {"urls": [FAKE_URL], "format": "html", "ttl": 0}
        if selectors:
            request["include_selectors"] = selectors
        await recorder.call("fetch", request, fake_response)
        print(recorder.path("fetch", request))


if __name__ == "__main__":
    asyncio.run(main())
