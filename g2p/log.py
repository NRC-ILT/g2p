"""
Error Log

"""

import logging
import os

import coloredlogs  # type: ignore

FIELD_STYLES = dict(
    levelname=dict(color="green"),
)


def setup_logger(name):
    """Create logger and configure with cool colors!"""

    logger = logging.getLogger(name)
    coloredlogs.install(
        level=os.environ.get("G2P_LOGLEVEL", "INFO").upper(),
        fmt="%(levelname)s - %(message)s",
        logger=logger,
        field_styles=FIELD_STYLES,
    )
    return logger


LOGGER = setup_logger("root")
