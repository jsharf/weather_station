import fire
import sys

from inky.auto import auto
from os.path import exists
from PIL import Image, ImageDraw

def display_image(display, filename=""):
    if not exists(filename):
        sys.stderr.write(f"Filename {filename} does not exist.\n")
        return
    with Image.open(filename) as im:
        draw = ImageDraw.Draw(im)
        # TODO(sharf): Do some overlay UI drawing here.

        print(display.resolution)
        print(im.size)
        im = im.resize(display.resolution)
        print(im.size)
        display.set_image(im)
        display.show()



def main(filename=""):
    display = auto()
    display_image(display, filename)


if __name__ == "__main__":
    fire.Fire(main)


