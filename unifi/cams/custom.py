import logging
import subprocess
import tempfile
from pathlib import Path

from unifi.cams.base import UnifiCamBase


class Custom(UnifiCamBase):
    def __init__(self, logger: logging.Logger, cert, token, host, opt) -> None:
        super().__init__(logger, cert, token, host, opt)
        self.event_id = 0
        self.snapshot_dir = tempfile.mkdtemp()
        self.snapshot_stream = None
        self.runner = None

        self.stream_source = dict()

        for i, stream_index in enumerate(["video1", "video2", "video3"]):
            self.stream_source[stream_index] = opt['source']

        self.snapshot_url = opt.get('snapshot-url')

    def start_snapshot_stream(self) -> None:
        if not self.snapshot_stream or self.snapshot_stream.poll() is not None:
            cmd = (
                self.snapshot_url
            )
            self.logger.info(f"Spawning stream for snapshots: {cmd}")
            self.snapshot_stream = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True
            )

    async def get_snapshot(self) -> Path:
        img_file = Path(self.snapshot_dir, "screen.jpg")
        if self.snapshot_url:
            await self.fetch_to_file(self.snapshot_url, img_file)
        else:
            self.start_snapshot_stream()
        return img_file

    async def run(self) -> None:
        return

    async def close(self) -> None:
        await super().close()
        if self.runner:
            await self.runner.cleanup()

        if self.snapshot_stream:
            self.snapshot_stream.kill()

    async def get_stream_source(self, stream_index: str) -> str:
        return self.stream_source[stream_index]

    async def start_video_stream(
        self, stream_index: str, stream_name: str, destination: tuple[str, int]
    ):
        has_spawned = stream_index in self._ffmpeg_handles
        is_dead = has_spawned and self._ffmpeg_handles[stream_index].poll() is not None

        resolution = ''

        if stream_index == "video1":
            resolution = "1920:1080"
        if stream_index == "video2":
            resolution = "1280:720"
        if stream_index == "video3":
            resolution = "640:360"
        # stream_i = int(stream_index[-1]) - 1
        # if stream_index == 'video1' and not has_spawned or is_dead:
        if not has_spawned or is_dead:
            source = await self.get_stream_source(stream_index)

            cmd = f"{source} {stream_index} {stream_name} {destination[0]} {destination[1]} {resolution}"
            if is_dead:
                self.logger.warn(f"Previous ffmpeg process for {stream_index} died.")

            self.logger.info(
                f"Spawning ffmpeg for {stream_index} ({stream_name}): {cmd}"
            )
            self._ffmpeg_handles[stream_index] = subprocess.Popen(
                cmd, shell=True
            )
