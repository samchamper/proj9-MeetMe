# proj8-Gcal
Snarf appointment data from a selection of a user's Google calendars, then display windows of free time based on user input of a minimum time window size.  

## Author:
Sam Champer  
schampe2@uoregon.edu  
With starter code from Michal Young.  


## What is this

A  Flask app that displays all the events from selected google calendars, after first getting authorization from google to fetch the calendars. The app then displays windows of free time based on user selection of a minimum time window size.  

## Usage

Run ```make install``` to install, then run ```make run``` to host the application. The app will be hosted to localhost:8000.  

## Nosetests

To run nosetests, first activate the virtual environment, then change directory to meetings and run nosetests:

```
. env/bin/activate
cd meetings
nosetests
```
