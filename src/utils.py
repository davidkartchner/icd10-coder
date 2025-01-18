import json
import logging
import re


def read_json(filepath):
    json_content = json.load(open(filepath))
    return json_content


def write_json(object, filepath):
    with open(filepath, "w") as f:
        json.dump(object, f, indent=2)


def get_codes(x):
    return [y["code"] for y in x["icd10_codes"]]


def get_code_and_status(input):
    """
    Compare two lists of tuples to see if the elements match
    """
    codes = set([(x["code"], x["status"]) for x in input["icd10_codes"]])


def setup_loggers(level=logging.INFO):
    """
    Sets up a logger with the specified logging level.
    Logs include the file name, line number, and timestamp.

    Args:
        level (int): The logging level (e.g., logging.DEBUG, logging.INFO).
    """
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


# def setup_loggers():
#     # Setup logging
#     logger = logging.getLogger("AgentLogger")
#     logger.setLevel(logging.DEBUG)

#     # File handler
#     file_handler = logging.FileHandler("agent_logs.log")
#     file_handler.setLevel(logging.DEBUG)

#     # Stream handler
#     stream_handler = logging.StreamHandler()
#     stream_handler.setLevel(logging.INFO)

#     # Formatter
#     formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
#     file_handler.setFormatter(formatter)
#     stream_handler.setFormatter(formatter)

#     # Add handlers to logger
#     logger.addHandler(file_handler)
#     logger.addHandler(stream_handler)
#     return logger


def check_icd10_validity(code):
    # ICD-10 format: one letter, followed by two digits, optionally followed by a period and 1-4 digits
    pattern = re.compile(r"^[A-Z][0-9]{2}(?:\.[0-9]{1,4})?$")
    return bool(pattern.match(code))
