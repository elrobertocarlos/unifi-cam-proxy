import json
import logging
import tempfile
from pathlib import Path

import aiohttp
from yarl import URL

from unifi.cams.base import UnifiCamBase


class ReolinkNVRCam(UnifiCamBase):
    def __init__(self, logger: logging.Logger, cert, token, host, opt) -> None:
        super().__init__(logger, cert, token, host, opt)
        self.snapshot_dir: str = tempfile.mkdtemp()
        self.motion_in_progress: bool = False

        self.ip = opt.get('ip')
        self.username = opt.get('username')
        self.password = opt.get('password')
        self.channel = opt.get('channel')

    async def get_snapshot(self) -> Path:
        img_file = Path(self.snapshot_dir, "screen.jpg")
        url = (
            f"http://{self.ip}"
            f"/api.cgi?cmd=Snap&user={self.username}&password={self.password}"
            f"&rs=6PHVjvf0UntSLbyT&channel={self.channel}"
        )
        await self.fetch_to_file(url, img_file)
        return img_file

    async def run(self) -> None:
        url = (
            f"http://{self.ip}"
            f"/api.cgi?user={self.username}&password={self.password}"
        )
        encoded_url = URL(url, encoded=True)

        body = (
            f'[{{ "cmd":"GetMdState", "param":{{ "channel":{self.channel} }} }}]'
        )
        while True:
            self.logger.info(f"Connecting to motion events API: {url}")
            try:
                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(None)
                ) as session:
                    while True:
                        async with session.post(encoded_url, data=body) as resp:
                            data = await resp.read()

                            try:
                                json_body = json.loads(data)
                                if "value" in json_body[0]:
                                    if json_body[0]["value"]["state"] == 1:
                                        if not self.motion_in_progress:
                                            self.motion_in_progress = True
                                            self.logger.info("Trigger motion start")
                                            await self.trigger_motion_start()
                                    elif json_body[0]["value"]["state"] == 0:
                                        if self.motion_in_progress:
                                            self.motion_in_progress = False
                                            self.logger.info("Trigger motion end")
                                            await self.trigger_motion_stop()
                                else:
                                    self.logger.error(
                                        "Motion API request responded with "
                                        "unexpected JSON, retrying. "
                                        f"JSON: {data}"
                                    )

                            except json.JSONDecodeError as err:
                                self.logger.error(
                                    "Motion API request returned invalid "
                                    "JSON, retrying. "
                                    f"Error: {err}, "
                                    f"Response: {data}"
                                )

            except aiohttp.ClientError as err:
                self.logger.error(f"Motion API request failed, retrying. Error: {err}")

    async def get_stream_source(self, stream_index: str) -> str:
        return (
            f"rtsp://{self.username}:{self.password}@{self.ip}:554"
            f"/h264Preview_{int(self.channel) + 1:02}_main"
        )
