# MeetMe
A web app designed to help groups of people coordinate common available free time in order to schedule meetings.  

## Author:
Sam Champer  
schampe2@uoregon.edu  
Uses some code from Michal Young.  

## About:
Here is a list of some features and bugs that I hereby allege to be features.  
Main things:
- This app is mostly democratic. The host of the event has the right to set certain initial values (event description, participant list, date range, and event duration), but otherwise is the host is not distinguished from other users.
- The app collects only anonymised, non-labeled event times from user calendars. Event details, other than times, are never stored in anything but temporary RAM. Events are stored in a database with only start and end times, not with titles. Additionally, events stored in the database are not associated with any specific user: events for all users are co-mingled. After submitting events, even the submitter of a list of events cannot see which times are unavailable because of their events specifically.
- Consequently, this app meets a high standard in terms of preservation of user data confidentiality. Other users may be able to make inferences about one another's schedules, especially for meetings with few people.
- The calendars and events list populate via AJAX. On one hand, this is cool. On the other, it can take quite a while to populate the lists, especially if a lot of calendars are checked. Since this process uses AJAX, it is not immediately apparant to users that the page is loading, so it may appear that the page is simply non-responsive. Some kind of loading indicator would be first on my list of features to add.  

Minor notes:
- Users attempting to join meetings where all users have already responded will be routed to the status page for the meeting.
- The app doesn't actively do anything after all users have responded. E.g., there is no special process for notifying users that everyone has responded. Users will have to check for themselves and then use some method of communication to determine which block of free time they want to schedule in. The app doesn't brush your teeth for you either.

## Usage

Run ```make install``` to install, then run ```make run``` to host the application. The app will be hosted to localhost:8000.  

## Nosetests

To run nosetests, first activate the virtual environment, then change directory to meetings and run nosetests:

```
. env/bin/activate
cd meetings
nosetests
```
