import io
import json
import os
import requests
import textwrap
import xmltodict

from dataclasses import dataclass
from datetime import datetime, timedelta, date
from dateutil import tz as tz
from inky.auto import auto
from PIL import Image, ImageDraw, ImageFont, ImageColor
from matplotlib import pyplot as plt

SATELLITE_URL = r'https://graphical.weather.gov/images/northeast/MaxT1_northeast.png'

WEATHER_URL = r'https://www.theweather.com/wimages/foto542cda2440863f662eba4e1b4a7cbdb6.png'
WEATHER_SMALL_URL = r'https://www.theweather.com/wimages/fotofa4eef0c623ca593933eb717316fffe2.png'
SUBWAY_MAP = r'Subway_Map.jpg'

TRUETYPE_FONT = r'/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf'

MTA_7_URL = r'https://otp-mta-prod.camsys-apps.com/otp/routers/default/nearby?stops=MTASBWY:721&apikey=2ctbNX4XX7oS5ywqVQT86DntRQQw59eB&groupByParent=true&routes=&timeRange=3600'

MTA_G_URL = r'https://otp-mta-prod.camsys-apps.com/otp/routers/default/nearby?stops=MTASBWY:G24&apikey=2ctbNX4XX7oS5ywqVQT86DntRQQw59eB&groupByParent=true&routes=&timeRange=3600'

# This is an esp32 webserver on the LAN. Serves timestamped CO2 readings on the
# root url.
CO2_PPM_URL = r'http://esp32.local/'
CO2_PPM_CACHE = r'./co2_ppm_samples.json'

def fetch_json(url):
    response = requests.get(url)
    return json.loads(response.content)

def fetch_xml(url):
    response = requests.get(url)
    return xmltodict.parse(response.content)

def overlay_timestamp(draw, font_size, offset):
    est = tz.gettz('America/New_York')
    now = datetime.now(est)
    font = ImageFont.truetype(TRUETYPE_FONT, font_size)
    date_string = now.strftime("%H:%M:%S")
    draw.rectangle([offset, (offset[0] + 140, offset[1] + 40)],
                   fill=ImageColor.getrgb("#C0FFEE"),
                   outline=ImageColor.getrgb("#D1E"))
    draw.text((offset[0] + 5, offset[1]), date_string, font=font, align="left", fill=ImageColor.getrgb("#007"))

def overlay_train_group(draw, group, y_offset, font_size=25):
    """ A group is a combo of (route, destination). """
    # First, let's grab the destination and route name.
    destination = find("headsign", group)
    route_id = find("route.id", group)
    route = route_id.split(":")[1]

    # Now, let's collect arrival times.
    times = group["times"]
    arrivals = [time["realtimeArrival"] for time in times]
    est = tz.gettz('America/New_York')
    today = date.today()
    start = datetime(today.year, today.month, today.day, tzinfo=est)
    arrival_strings = []
    now = datetime.now(est)
    last_time = datetime.min
    for time in arrivals:
        time_str = (timedelta(seconds=time))
        arrival = start + timedelta(seconds=time)
        if now + timedelta(minutes=3) > arrival:
            print(f"Ignoring arrival too soon: {arrival}")
            continue
        arrival_string = arrival.strftime(":%M") if last_time.hour == arrival.hour else arrival.strftime("%I:%M")
        if last_time == datetime.min:
            arrival_string = arrival.strftime("%I:%M")
        arrival_strings.append(arrival_string)
        last_time = arrival

    x_offset = 10
    width = 330
    padding_x = 5
    padding_y = 5
    height = font_size + padding_y * 2
    group_summary = f"{destination} ({route}) | {', '.join(arrival_strings)}"
    lines = textwrap.wrap(group_summary, width=27)
    font = ImageFont.truetype(TRUETYPE_FONT, font_size)
    text_height = sum([font.getsize(line)[1] for line in lines])
    height = text_height + padding_y * 2
    draw.rectangle([(x_offset, y_offset), (x_offset + width, y_offset + height)],
                   fill=ImageColor.getrgb("#C0FFEE"),
                   outline=ImageColor.getrgb("#D1E"))
    for line in lines:
        draw.text((x_offset + padding_x, y_offset + padding_y), line, font=font, align="left", fill=ImageColor.getrgb("#007"))
        y_offset += font.getsize(line)[1]
    print(group_summary)
    return height

def overlay_image(bg_image, fg_image, offset):
    bg_image.paste(im=fg_image, box=offset)

def find(element, obj):
    """ Use a period-separated path to index elements in a nested dictionary. """
    keys = element.split('.')
    rv = obj
    for key in keys:
        rv = rv[key]
    return rv

@dataclass
class Co2Sample:
  timestamp: datetime
  co2_ppm: float

def refresh_co2_ppm_cache():
    CO2_PPM_URL 
    response = requests.get(CO2_PPM_URL)
    samples = []
    for sample_str in response.content.split('\n'):
        sample_str = sample_str.strip()
        (timestamp, co2_ppm) = sample_str.split(',')
        # Parse the timestamp. D/M/Y H:M:S
        samples.append(Co2Sample(datetime.strptime(timestamp, "%d/%m/%Y %H:%M:%S"), float(co2_ppm)))
    # If the cache file doesn't exist, create it.
    if not os.path.exists(CO2_PPM_CACHE):
        with open(CO2_PPM_CACHE, 'w') as f:
            pass # Empty file.
    # Append the samples to a cache file.
    with open(CO2_PPM_CACHE, 'a') as f:
        for sample in samples:
            f.write(f"{sample.timestamp},{sample.co2_ppm}\n")

def get_co2_ppm_cache():
    results = []
    with open(CO2_PPM_CACHE, 'r') as f:
        for sample_str in f.readlines():
            (timestamp, co2_ppm) = sample_str.split(',')
            results.append(Co2Sample(datetime.strptime(timestamp, "%d/%m/%Y %H:%M:%S"), float(co2_ppm)))
    # Sort the results by time.
    results.sort(key=lambda x: x.timestamp)
    return results

def co2_ppm_graph_image(co2_ppm_samples):
    """
    Generate a graph of CO2 ppm samples.
    """
    fig, ax = plt.subplots()
    ax.plot([sample.timestamp for sample in co2_ppm_samples], [sample.co2_ppm for sample in co2_ppm_samples])
    ax.set_xlabel('Time')
    ax.set_ylabel('CO2 ppm')
    ax.set_title('CO2 ppm')
    # Render the graph to an image. Then call overlay_image to overlay it on the background image.
    image = Image.frombytes('RGB', fig.canvas.get_width_height(),
                            fig.canvas.tostring_rgb())
    return image

def main():
    display = auto()
    MTA_7_data = fetch_json(MTA_7_URL)[0]
    MTA_G_data = fetch_json(MTA_G_URL)[0]

    groups = find("groups", MTA_7_data)
    groups.extend(find("groups", MTA_G_data))

    # Display panel showing the weather.
    weather_request = requests.get(url=WEATHER_SMALL_URL)
    weather_file = io.BytesIO(weather_request.content)
    weather_widget = Image.open(weather_file)
    weather_widget = weather_widget.resize((250, 448))

    refresh_co2_ppm_cache()
    co2_ppm_samples = get_co2_ppm_cache()
    co2_ppm_graph = co2_ppm_graph_image(co2_ppm_samples)

    with Image.open(SUBWAY_MAP) as im:
        im = im.resize(display.resolution)
        overlay_image(im, weather_widget, (350, 0))
        overlay_image(im, co2_ppm_graph, (0, 200))
        draw = ImageDraw.Draw(im)
        overlay_timestamp(draw, font_size=25, offset=(450, 390))
        y_offset = 20
        for i, group in enumerate(groups):
            height = overlay_train_group(draw, group, y_offset, font_size=20)
            y_offset += height + 10
        display.set_image(im)
        display.show()


if __name__ == "__main__":
    main()
