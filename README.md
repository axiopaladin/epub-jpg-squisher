Use this simple python script to prepare EPUB files for your e-reader. All images are resized, compressed to monochrome, and rotated (except the cover) to fit the pixel dimensions listed at the top of the script.
The defaults are designed to accomodate landscape reading on a 480x800 display. Images 128px or smaller on their longest dimension are not rotated.

# Installation
Assuming an Ubuntu-based linux distro (or WSL/VM):
1. Install imagemagick: `sudo apt install imagemagick`
2. (Optional: Create a venv for the python requirements `python3 -m venv .venv; source .venv/bin/activate`)
3. Install python requirements: `pip3 install -r requirements.txt`

# Usage
`./squish_jpegs.py input_file.epub output_file.epub`
