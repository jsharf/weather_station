import io
import json
import requests
import xmltodict

from datetime import datetime, timedelta, date
from dateutil import tz as tz
from inky.auto import auto
from PIL import Image, ImageDraw, ImageFont, ImageColor


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

def overlay_train_group(draw, group, y_offset, font_size=18):
    """ A group is a combo of (route, destination). """
    # First, let's grab the destination and route name.
    destination = find("headsign", group)
    route_id = find("route.id", group)
    route = route_id.split(":")[1]
    print(f"Group headed to {destination} on route {route}.")

    # Now, let's collect arrival times.
    times = group["times"]
    arrivals = [time["realtimeArrival"] for time in times]
    est = tz.gettz('America/New_York')
    today = date.today()
    start = datetime(today.year, today.month, today.day, tzinfo=est)
    arrival_strings = []
    now = datetime.now(est)
    for time in arrivals:
        time_str = (timedelta(seconds=time))
        arrival = start + timedelta(seconds=time)
        if arrival < now:
            print(f"Ignoring arrival in the past: {arrival}")
            continue
        arrival_in = arrival - now
        arrival_strings.append(str(arrival_in.seconds//60))

    x_offset = 10
    width = 200
    height = 22
    padding = 2
    draw.rectangle([(x_offset, y_offset), (x_offset + width, y_offset + height)],
                   fill=ImageColor.getrgb("#C0FFEE"),
                   outline=ImageColor.getrgb("#D1E"))
    font = ImageFont.truetype(TRUETYPE_FONT, font_size)
    group_summary = f"{destination} ({route}) | {', '.join(arrival_strings)}"
    draw.text((x_offset + padding, y_offset + padding), group_summary, font=font, align="left", fill=ImageColor.getrgb("#007"))
    print(group_summary)

def overlay_image(bg_image, fg_image, offset):
    bg_image.paste(im=fg_image, box=(250, 100))

def find(element, obj):
    """ Use a period-separated path to index elements in a nested dictionary. """
    keys = element.split('.')
    rv = obj
    for key in keys:
        rv = rv[key]
    return rv

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

    with Image.open(SUBWAY_MAP) as im:
        im = im.resize(display.resolution)
        overlay_image(im, weather_widget, (350, 100, 600, 440))
        draw = ImageDraw.Draw(im)
        for i, group in enumerate(groups):
            overlay_train_group(draw, group, 20 + i * 25)
        display.set_image(im)
        display.show()



if __name__ == "__main__":
    main()
