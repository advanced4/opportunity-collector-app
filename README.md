# Overview
This is a simple little program to facilitate getting the latest opportunities from grants.gov
and sam.gov. The program is intended to provide a simplified subset of possible filters 
provided by the source APIs, making it easier to use.

## Features
* Retains settings/configuration between usage. Typically you will configure these once
to your needs, and it will stay that way on each usage
* Will alert you when your sam.gov API key expires (its only guess based on when key was provided)
* sam.gov is optional
* Easy setup. It will guide you through setting up your sam.gov api key if you choose to use that feature

# Installation
## Pre-built binaries
See the releases page to download precompiled binaries for your platform.

### Windows
Is a self contained exe that can be ran by double clicking it

### Linux
Is a self contained ELF file that can be executed

### Mac
Is a zip archive containing an application (a *.app folder). Extract the application,
place it in your Applications folder, and double click

## From Source
Note: this was written in Python 3.8, but probably works on any python3.X
1. `git clone https://github.com/advanced4/opportunity-collector`
2. `cd opportunity-collector`
3. `pip install tkinter requests` (may not be needed. some python distributions include both, one, or none of these)
4. `python opp_gui.py`

# Notes
I'm not an application GUI programmer so keep that in mind. It's not the prettiest,
 but should be acceptable & functional.

## grants.gov
* eligibilities: all government entities & tribal entities are omitted as these are uncommon
and their omission helps keep the UI less noisy 


# CLI Versions
Included in this repository are two prior CLI versions for sam.gov & grants.gov respectively. They
are *not* for production usage, but merely provided in case a developer/software engineering minded
person wants to work off of them. They are no where near as polished as opps_gui.py. I imagine setting these as a cron job would be useful. This
may be a future project, if there's enough interest.

# Known Issues
1. The **window** does not dynamically resize when adding NAICS codes, but the elements do. If many
NAICS codes are added, eventually things will get pushed outside the window/be squished. Simply
manually resizing the window fixes it. It will draw everything correctly on start, so after 
adding the NAICS codes (typically a one time thing), then all subsequent usage should look fine.

# License
MIT