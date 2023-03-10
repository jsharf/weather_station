import io
import json
import logging
import matplotlib
import os
import requests
import textwrap
import xmltodict

from co2_samples import *

from datetime import datetime, timedelta, date
from dateutil import tz as tz
from inky.auto import auto
from matplotlib import pyplot as plt
from PIL import Image, ImageDraw, ImageFont, ImageColor

logger = logging.getLogger(__name__)

SATELLITE_URL = r'https://graphical.weather.gov/images/northeast/MaxT1_northeast.png'

WEATHER_URL = r'https://www.theweather.com/wimages/foto542cda2440863f662eba4e1b4a7cbdb6.png'
WEATHER_SMALL_URL = r'https://www.theweather.com/wimages/fotofa4eef0c623ca593933eb717316fffe2.png'
SUBWAY_MAP = r'Subway_Map.jpg'

TRUETYPE_FONT = r'/usr/share/fonts/truetype/noto/NotoSansMono-Regular.ttf'

MTA_7_URL = r'https://otp-mta-prod.camsys-apps.com/otp/routers/default/nearby?stops=MTASBWY:721&apikey=2ctbNX4XX7oS5ywqVQT86DntRQQw59eB&groupByParent=true&routes=&timeRange=3600'

MTA_G_URL = r'https://otp-mta-prod.camsys-apps.com/otp/routers/default/nearby?stops=MTASBWY:G24&apikey=2ctbNX4XX7oS5ywqVQT86DntRQQw59eB&groupByParent=true&routes=&timeRange=3600'

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

def image_from_plt_fig(fig):
    buf = io.BytesIO()
    fig.savefig(buf)
    buf.seek(0)
    return Image.open(buf)

def main():
    logging.basicConfig(level=logging.INFO)
    display = auto()
    refresh_co2_ppm_cache()
    co2_ppm_samples = get_co2_ppm_cache()
    # Filter only samples from the last week.
    est = tz.gettz('America/New_York')
    co2_ppm_samples = [sample for sample in co2_ppm_samples if (datetime.now(est) - sample.timestamp) < timedelta(hours=120)]
    if len(co2_ppm_samples) == 0:
        logger.info(f"No sensor samples to graph.")
        return
    co2_ppm_graph_buf = co2_ppm_graph_image(co2_ppm_samples)
    co2_ppm_graph = Image.open(co2_ppm_graph_buf)
    co2_ppm_graph = co2_ppm_graph.resize(display.resolution)

    # If the CO2 PPM is above 1000, access the shelly smart socket at IP 192.168.0.190 and turn on the fan.
    # If the CO2 PPM has fallen below 600, we can shut the fan off.
    # Numbers updated after Lexie movin to better accomodate 2 people.
    if co2_ppm_samples[-1].co2_ppm > 1100:
        requests.get(url="http://192.168.0.190/relay/0?turn=on")
    elif co2_ppm_samples[-1].co2_ppm < 600:
        requests.get(url="http://192.168.0.190/relay/0?turn=off")

    with Image.open(SUBWAY_MAP) as im:
        im = im.resize(display.resolution)
        overlay_image(im, co2_ppm_graph, (0, 0))
        draw = ImageDraw.Draw(im)
        overlay_timestamp(draw, font_size=25, offset=(450, 10))
        display.set_image(im)
        display.show()


if __name__ == "__main__":
    main()
