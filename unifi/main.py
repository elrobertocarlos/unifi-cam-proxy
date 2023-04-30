import argparse
import asyncio
import logging
import sys
from shutil import which

import coloredlogs
from pyunifiprotect import ProtectApiClient
import yaml
from yaml.loader import SafeLoader

from unifi.cams import (
    DahuaCam,
    FrigateCam,
    HikvisionCam,
    Reolink,
    ReolinkNVRCam,
    RTSPCam,
    Custom,
)
from unifi.core import Core

CAMS = {
    "amcrest": DahuaCam,
    "dahua": DahuaCam,
    "frigate": FrigateCam,
    "hikvision": HikvisionCam,
    "lorex": DahuaCam,
    "reolink": Reolink,
    "reolink_nvr": ReolinkNVRCam,
    "rtsp": RTSPCam,
    "custom": Custom,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=False, help="Config file path", default="config.yaml")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="increase output verbosity"
    )
    return parser.parse_args()


async def generate_token(host, nvr_username, nvr_password, logger):
    response = {}
    try:
        protect = ProtectApiClient(
            host, 443, nvr_username, nvr_password, verify_ssl=False
        )
        await protect.update()
        response = await protect.api_request("cameras/manage-payload")
        return response["mgmt"]["token"]
    except Exception:
        logger.exception(
            "Could not automatically fetch token."
        )
        return None
    finally:
        await protect.close_session()


async def run():
    args = parse_args()

    config = {}

    # cameras = []
    with open(args.config) as f:
        config = yaml.load(f, Loader=SafeLoader)

    print(config)

    cert = config['cert']
    host = config['host']
    nvr_username = config.get('nvr_username')
    nvr_password = config.get('nvr_password')
    token = config.get('token')

    main_logger = logging.getLogger("main")

    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG
    coloredlogs.install(level=level, logger=main_logger)

    # Preflight checks
    for binary in ["ffmpeg", "nc"]:
        if which(binary) is None:
            main_logger.error(f"{binary} is not installed")
            sys.exit(1)

    if not token:
        token = await generate_token(host, nvr_username, nvr_password, main_logger)

    if not token:
        main_logger.error("A valid token is required")
        sys.exit(1)

    camera_connections = []

    for (camera_name) in config['cameras']:
        print(camera_name)
        opt = config['cameras'][camera_name]
        print(opt['type'])
        klass = CAMS[opt['type']]
        camera_logger = logging.getLogger(camera_name)
        cam_instance = klass(camera_logger, cert, token, host, opt)
        coloredlogs.install(level=level, logger=camera_logger)
        c = Core(camera_logger, cert, host, token, opt, cam_instance)
        camera_connections.append(asyncio.create_task(c.run()))
    main_logger.info("All cameras processed, waiting :D!")
    await asyncio.gather(*camera_connections)


def main():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run())


if __name__ == "__main__":
    main()
    main()
