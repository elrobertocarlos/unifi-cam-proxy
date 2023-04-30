import logging
import subprocess
import tempfile
from pathlib import Path

from aiohttp import web

from unifi.cams.base import UnifiCamBase


class RTSPCam(UnifiCamBase):
    def __init__(self, logger: logging.Logger, cert, token, host, opt) -> None:
        super().__init__(logger, cert, token, host, opt)
        self.event_id = 0
        self.snapshot_dir = tempfile.mkdtemp()
        self.snapshot_stream = None
        self.runner = None
        self.stream_source = dict()

        self.snapshot_url = opt.get('snapshot_url')
        self.rtsp_transport = opt.get('rtsp_transport', 'tcp')

        for i, stream_index in enumerate(["video1", "video2", "video3"]):
            # if not i < len(opt['source']):
            #     i = -1
            self.stream_source[stream_index] = opt['source']
        if not self.snapshot_url:
            self.start_snapshot_stream()

        self.http_api = opt.get('http_api', 0)

    def start_snapshot_stream(self) -> None:
        if not self.snapshot_stream or self.snapshot_stream.poll() is not None:
            cmd = (
                f"ffmpeg -hide_banner -nostdin -y -re -rtsp_transport {self.rtsp_transport} "
                f'-i "{self.stream_source["video1"]}" '
                "-r 1 "
                f"-update 1 {self.snapshot_dir}/screen.jpg"
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
        if self.http_api:
            self.logger.info(f"Enabling HTTP API on port {self.http_api}")

            app = web.Application()

            async def start_motion(request):
                self.logger.debug("Starting motion")
                await self.trigger_motion_start()
                return web.Response(text="ok")

            async def stop_motion(request):
                self.logger.debug("Starting motion")
                await self.trigger_motion_stop()
                return web.Response(text="ok")

            app.add_routes([web.get("/start_motion", start_motion)])
            app.add_routes([web.get("/stop_motion", stop_motion)])

            self.runner = web.AppRunner(app)
            await self.runner.setup()
            site = web.TCPSite(self.runner, port=self.http_api)
            await site.start()

    async def close(self) -> None:
        await super().close()
        if self.runner:
            await self.runner.cleanup()

        if self.snapshot_stream:
            self.snapshot_stream.kill()

    async def get_stream_source(self, stream_index: str) -> str:
        return self.stream_source[stream_index]
