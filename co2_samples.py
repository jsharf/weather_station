import logging
import matplotlib
import matplotlib.pyplot as plt
import os
import requests

from appdirs import user_cache_dir
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from dateutil import tz as tz
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DIR = r'home_station'

# This is an esp32 webserver on the LAN. Serves timestamped CO2 readings on the
# root url.
CO2_PPM_URL = r'http://esp32.local/'
CO2_PPM_CACHE = r'co2_ppm_samples.csv'

@dataclass
class Co2Sample:
  timestamp: datetime
  co2_ppm: float

def refresh_co2_ppm_cache():
    try:
        response = requests.get(CO2_PPM_URL)
    except requests.exceptions.RequestException as e:
        logger.error(e)
        return

    samples = []
    response_lines = response.content.split(b"\n")
    logger.info(f"lines: {len(response_lines)}")
    for sample_str in response_lines:
        logger.info(f"line: {sample_str}")
        sample_str = sample_str.decode("utf-8").strip()
        try:
            (timestamp, co2_ppm_str) = sample_str.split(",")
        except ValueError as e:
            logger.info(f"Could not parse line {sample_str}: {e}")
            break
        logger.info(f"Received: {sample_str}")
        # Parse the timestamp. D/M/Y H:M:S
        try:
            co2_ppm_str = co2_ppm_str.strip()
            (co2_ppm, unit) = co2_ppm_str.split(" ")
            if unit == "ppm":
                samples.append(Co2Sample(datetime.strptime(str(timestamp), "%d/%m/%Y %H:%M:%S (%Z)"), float(co2_ppm)))
                logger.info(f"Parsed: {str(samples[-1])}")
        except ValueError as e:
            logger.error(f"Could not parse sample: {sample_str}: {e}")
    # If the cache file doesn't exist, create it.
    cache_dir = user_cache_dir(CACHE_DIR)
    Path(cache_dir).mkdir(exist_ok=True)
    cache_file = f"{cache_dir}/{CO2_PPM_CACHE}"
    if not os.path.exists(cache_file):
        with open(cache_file, 'w') as f:
            pass # Empty file.
    # Append the samples to a cache file.
    with open(cache_file, 'a') as f:
        for sample in samples:
            f.write(f"{sample.timestamp},{sample.co2_ppm}\n")
    # If the file is larger than 5MB, rename it and start a new one.
    if os.path.getsize(cache_file) > 5 * 1024 * 1024:
        os.rename(cache_file, f"{cache_file}.{datetime.now().strftime('%Y%m%dT%H%M%S')}")
        with open(cache_file, 'w') as f:
            pass # Empty file.

def get_co2_ppm_cache():
    results = []
    cache_dir = user_cache_dir(CACHE_DIR)
    cache_file = f"{cache_dir}/{CO2_PPM_CACHE}"
    with open(cache_file, 'r') as f:
        for sample_str in f.readlines():
            (timestamp, co2_ppm) = sample_str.split(',')
            results.append(Co2Sample(datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S"), float(co2_ppm)))
    # Sort the results by time.
    results.sort(key=lambda x: x.timestamp)
    return results

def get_entire_co2_ppm_cache():
    """ Get all CO2 ppm samples from the cache.
    
    Like get_co2_ppm_cache, but also fetches historical data from the cache
    directory and merges it.
    """
    results = []
    cache_dir = user_cache_dir(CACHE_DIR)
    cache_file = f"{cache_dir}/{CO2_PPM_CACHE}"
    for filename in os.listdir(cache_dir):
        if not filename.startswith(CO2_PPM_CACHE):
            continue
        with open(f"{cache_dir}/{filename}", 'r') as f:
            for sample_str in f.readlines():
                (timestamp, co2_ppm) = sample_str.split(',')
                results.append(Co2Sample(datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S"), float(co2_ppm)))
    # Sort the results by time.
    results.sort(key=lambda x: x.timestamp)
    return results

def co2_ppm_graph_image(co2_ppm_samples):
    """
    Generate a graph of CO2 ppm samples.
    """
    matplotlib.rc('xtick', labelsize=18)
    matplotlib.rc('ytick', labelsize=15)
    fig, ax = plt.subplots()
    times = [-(datetime.now() - sample.timestamp).total_seconds()/3600 for sample in co2_ppm_samples]
    co2_ppm = [sample.co2_ppm for sample in co2_ppm_samples]
    ax.plot(times, co2_ppm)
    ax.set_xlabel('Time')
    ax.set_ylabel('CO2 ppm')
    ax.set_title('CO2 ppm')
    ax.axhline(y=1000, color='r', linestyle='-')
    return fig
