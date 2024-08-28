# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 15.08.2024                    #
# ========================================= #

import logging

def setup_logging(log_level=logging.INFO):
    # Sets up logging for the bot with the specified log level
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=log_level
    )
    logging.info("Logging is set up.")

def get_logger(name: str) -> logging.Logger:
    # Retrieves a logger by name
    return logging.getLogger(name)
