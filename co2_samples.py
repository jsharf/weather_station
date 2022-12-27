import logging
import matplotlib
import matplotlib.pyplot as plt
import seaborn
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
  temp_c: float
  rel_humidity: float

def parse_sample(sample_str):
    try:
        (timestamp, co2_ppm_str, temp_c, rel_humidity) = sample_str.split(",")
    except ValueError as e:
        logger.info(f"Could not parse line {sample_str}: {e}")
        return None
    logger.info(f"Received: {sample_str}")
    # Parse the timestamp. D/M/Y H:M:S
    try:
        co2_ppm_str = co2_ppm_str.strip()
        (co2_ppm, unit) = co2_ppm_str.split(" ")
        temp_str = temp_c.strip()
        (temp_c, _) = temp_str.split(" ")
        rel_humidity_str = rel_humidity.strip()
        (rel_humidity, _) = rel_humidity_str.split(" ")
        if unit != "ppm":
            return None
        return Co2Sample(datetime.strptime(str(timestamp), "%d/%m/%Y %H:%M:%S (%Z)"), float(co2_ppm), float(temp_c), float(rel_humidity))
    except ValueError as e:
        logger.error(f"Could not parse sample: {sample_str}: {e}")
        return None

def refresh_co2_ppm_cache():
    try:
        response = requests.get(CO2_PPM_URL)
    except requests.exceptions.RequestException as e:
        logger.error(e)
        return

    samples = []
    response_lines = response.content.split(b"\n")
    for sample_str in response_lines:
        sample_str = sample_str.decode("utf-8").strip()
        samples.append(parse_sample(sample_str))
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
            results.append(parse_sample(sample_str))
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
                results.append(Co2Sample(datetime.strptime(timestamp, "%Y/%m/%d %H:%M:%S (%Z)"), float(co2_ppm)))
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
    temp = [sample.temp_c for sample in co2_ppm_samples]
    rel_humidity = [sample.rel_humidity for sample in co2_ppm_samples]
    # Plot CO2_PPM, temperature and relative humidity on different axes.
    ax.plot(times, co2_ppm, label="CO2 ppm", color='b')
    ax2 = ax.twinx()
    ax2.plot(times, temp, label="Temperature (C)", color='g')
    ax3 = ax.twinx()
    ax3.plot(times, rel_humidity, label="Relative Humidity (%)", color='r')
    ax.set_xlabel("Time (hours ago)", fontsize=18)
    ax.set_ylabel("CO2 ppm", fontsize=18)
    ax.set_title("CO2 ppm over time", fontsize=18)
    ax.legend(fontsize=18)
    ax.grid()
    # Draw threshold horizontal lines for 800 CO2 ppm and 450 CO2 ppm.
    ax.axhline(y=800, color='r', linestyle='--')
    ax.axhline(y=450, color='r', linestyle='--')
    return fig
