import logging
import tempfile
from pathlib import Path

import httpx
from amcrest import AmcrestCamera
from amcrest.exceptions import CommError

from unifi.cams.base import RetryableError, SmartDetectObjectType, UnifiCamBase


class DahuaCam(UnifiCamBase):
    def __init__(self, logger: logging.Logger, cert, token, host, opt) -> None:
        super().__init__(logger, cert, token, host, opt)
        self.snapshot_dir = tempfile.mkdtemp()

        self.channel = opt.get('channel')
        self.snapshot_channel = opt.get('snapshot_channel', self.channel - 1)
        self.motion_index = opt.get('motion_index', self.snapshot_channel)

        self.ip = opt.get('ip')
        self.username = opt.get('username')
        self.password = opt.get('password')

        self.camera = AmcrestCamera(
            self.ip, 80, self.username, self.password
        ).camera

        self.main_stream = opt.get('main_stream')
        self.sub_stream = opt.get('sub_stream')

    async def get_snapshot(self) -> Path:
        img_file = Path(self.snapshot_dir, "screen.jpg")
        try:
            snapshot = await self.camera.async_snapshot(
                channel=self.snapshot_channel
            )
            with img_file.open("wb") as f:
                f.write(snapshot)
        except CommError as e:
            self.logger.warning("Could not fetch snapshot", exc_info=e)
            pass
        return img_file

    async def run(self) -> None:
        if self.motion_index == -1:
            return
        while True:
            self.logger.info("Connecting to motion events API")
            try:
                async for event in self.camera.async_event_actions(
                    eventcodes="VideoMotion,SmartMotionHuman,SmartMotionVehicle"
                ):
                    code = event[0]
                    action = event[1].get("action")
                    index = event[1].get("index")

                    if not index or int(index) != self.motion_index:
                        self.logger.debug(f"Skipping event {event}")
                        continue

                    object_type = None
                    if code == "SmartMotionHuman":
                        object_type = SmartDetectObjectType.PERSON
                    elif code == "SmartMotionVehicle":
                        object_type = SmartDetectObjectType.VEHICLE

                    if action == "Start":
                        self.logger.info(f"Trigger motion start for index {index}")
                        await self.trigger_motion_start(object_type)
                    elif action == "Stop":
                        self.logger.info(f"Trigger motion end for index {index}")
                        await self.trigger_motion_stop()
            except (CommError, httpx.RequestError):
                self.logger.error("Motion API request failed, retrying")

    async def get_stream_source(self, stream_index: str) -> str:
        if stream_index == "video1":
            subtype = self.main_stream
        else:
            subtype = self.sub_stream
        try:
            return await self.camera.async_rtsp_url(
                channel=self.channel, typeno=subtype
            )
        except (CommError, httpx.RequestError):
            raise RetryableError("Could not generate RTSP URL")
