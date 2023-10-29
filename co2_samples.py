import logging
import io
import os
import requests

import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns

from appdirs import user_cache_dir
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from dateutil import tz as tz
from pathlib import Path

est = tz.gettz('America/New_York')

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
        (timestamp_str, co2_ppm_str, temp_c, rel_humidity) = sample_str.split(",")
    except ValueError as e:
        logger.info(f"Could not parse line {sample_str}: {e}")
        return None
    logger.info(f"Received: {sample_str}")
    try:
        co2_ppm_str = co2_ppm_str.strip()
        (co2_ppm, unit) = co2_ppm_str.split(" ")
        temp_str = temp_c.strip()
        (temp_c, _) = temp_str.split(" ")
        rel_humidity_str = rel_humidity.strip()
        (rel_humidity, _) = rel_humidity_str.split(" ")
        if unit != "ppm":
            return None
        # Parse the timestamp. D/M/Y H:M:S
        timestamp = datetime.strptime(str(timestamp_str), "%d/%m/%Y %H:%M:%S (%Z)")
        NYC = tz.gettz("America/New_York")
        timestamp = timestamp.replace(tzinfo=NYC)
        return Co2Sample(timestamp, float(co2_ppm), float(temp_c), float(rel_humidity))
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
        sample = parse_sample(sample_str)
        if sample is None:
            continue
        samples.append(sample)
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
            f.write(sample.timestamp.strftime("%d/%m/%Y %H:%M:%S (%Z)") + f",{sample.co2_ppm} ppm,{sample.temp_c} C,{sample.rel_humidity} rel_humidity\n")
    # If the file is larger than 5MB, rename it and start a new one.
    if os.path.getsize(cache_file) > 5 * 1024 * 1024:
        os.rename(cache_file, f"{cache_file}.{datetime.now(est).strftime('%Y%m%dT%H%M%S')}")
        with open(cache_file, 'w') as f:
            pass # Empty file.

def get_co2_ppm_cache():
    results = []
    cache_dir = user_cache_dir(CACHE_DIR)
    cache_file = f"{cache_dir}/{CO2_PPM_CACHE}"
    with open(cache_file, 'r') as f:
        for sample_str in f.readlines():
            sample = parse_sample(sample_str)
            if sample is None:
                continue
            results.append(sample)
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
                sample = parse_sample(sample_str)
                if sample is None:
                    continue
                results.append(sample)
    # Sort the results by time.
    results.sort(key=lambda x: x.timestamp)
    return results

def co2_ppm_graph_image(co2_ppm_samples):
    """
    Generate a graph of CO2 ppm samples, Temperature C and Relative Humidity all in the same graph.
    Use seaborn to make the graph look nice.

    Graphs with more than one axis are a bit tricky to get right. The x-axis is shared between the
    two axes, but the y-axis is not. The y-axis for the temperature and relative humidity are
    fixed to the range 0-100, but the y-axis for the CO2 ppm is fixed to the range 0-2000.
    """
    times = [-(datetime.now(est) - sample.timestamp).total_seconds()/3600 for sample in co2_ppm_samples]
    co2_ppm = [sample.co2_ppm for sample in co2_ppm_samples]
    temp = [sample.temp_c for sample in co2_ppm_samples]
    rel_humidity = [sample.rel_humidity for sample in co2_ppm_samples]
    # Use seaborn.
    # Plot CO2_PPM, temperature and relative humidity on different axes.
    # Draw CO2 threshold horizontal lines at 510 and 800ppm.
    # Use color blind friendly colors.
    
    # Set the style.
    sns.set_style("darkgrid")
    # Set the color palette.
    sns.set_palette("colorblind")
    # Set the figure size.
    fig = plt.figure(figsize=(10, 6))
    # Create the axes.
    ax1 = fig.add_subplot(111)
    ax2 = ax1.twinx()
    # Plot the data.
    ax1.plot(times, co2_ppm, color="tab:blue", label="CO2 ppm")
    ax2.plot(times, temp, color="tab:orange", label="Temperature C")
    ax2.plot(times, rel_humidity, color="tab:green", label="Relative Humidity")
    # Set the x-axis label.
    ax1.set_xlabel("Time (hours ago)")
    # Set the y-axis labels.
    ax1.set_ylabel("CO2 ppm")
    ax2.set_ylabel("Temperature C / Relative Humidity")
    # Set the y-axis limits.
    ax1.set_ylim(0, 2000)
    ax2.set_ylim(0, 100)
    # Set the x-axis range. Scale it to the data.
    ax1.set_xlim(min(times), max(times))
    # Draw the CO2 threshold lines.
    ax1.axhline(y=600, color="tab:red", linestyle="--")
    ax1.axhline(y=1100, color="tab:red", linestyle="--")
    # Set the legend.
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    # Save the figure to a buffer.
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    buf.seek(0)
    # Return the buffer.
    return buf
