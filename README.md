# ECE1779 Project #2: Megaphone

_A location-based, community-driven question and answer service built atop Google App Engine._

## Group Information

- Group Number 5
- Group members:
    - David Carney
    - Ahmadul Hassan

## Work Breakdown

We feel that there was a 50-50 split in work/effort between the two group memebers. Please don't hesitate to ask for further details about the (long list of) tasks. We believe, however, that this is immaterial since we both agree that work was evenly divided.

## Account Instructions

Provided by email. Assuming you have the necessary permissions, you can access
the project [here](http://valued-pact-89315.appspot.com/).

## In-Class Presentation

Available [here](https://docs.google.com/presentation/d/1F7dg6Mazm-ZZaqPfnyF5OAsLoArRABiZPpyZ2iMjHOE/edit?usp=sharing).

## Code Repository

See https://github.com/dfcarney/ece1779

<!-- ([This document](https://github.com/dfcarney/ece1779/tree/master/project-2) is also on GitHub). -->

## Application Overview

Megaphone is designed to be a simple service that allows (authenticated) users
to post and receive answers to location-based questions. In our initial 
implementation we only provide location-based search for world-readable questions.
Answers can only be submitted by any authenticated user.

All users see the following links in the header after logging in:

- **Nearby Activity**: Provides a list of nearby questions, with a location-based search interface.
- **My Activity**: Provides a list of the user's questions, with a location-based filter.
- **Profile**: Used to configure user settings. Currently, limited to configuring the Prospective Search area (see below for details).
- **Logout**

## Employed Technologies/Services

Here is the summary of (previously mentioned) Google App Engine technologies 
employed by Megaphone:

- Users [https://cloud.google.com/appengine/docs/python/users/]
- Deferred background jobs [https://cloud.google.com/appengine/articles/deferred]
- Channel API [https://cloud.google.com/appengine/docs/python/channel/]
- Search (specifically, building an index for use with GeoPoint searches) [https://cloud.google.com/appengine/docs/python/search/]
- Prospective Search [https://cloud.google.com/appengine/docs/python/prospectivesearch/]
- Memcached [https://cloud.google.com/appengine/docs/python/memcache/]

_**IMPORTANT**: the user must grant the browser permission to access his/her location for Megaphone to work as intended._

## Main Features

**User Authentication**

Though not really a feature per se, this is an important component. For this Megaphone
leverages Google App Engine's *Users API*.

_APIs employed: Users._


**Ask Question, Post Answers, Accept Answer**

Users can ask multiple 
questions. Doing so is encapsulated by creating a `Question` object. In addition
to the body of the question and a timestamp, each question has a location 
obtained from the browser (i.e. the HTML5 Geolocation API). Once created, any 
authenticated user can post `Answers` to any question. Answers also have a 
location associated with them. The owner of a question can *accept* one of 
the provided answers.

Note that objects (entities) are persisted using the *NDB Datastore* (and the
corresponding Python API).

_APIs employed: NDB Datastore (synchronous, asynchronous)._


**(Retroactive) Location-based Question Search**

The *Nearby Activity* page contains a simple, location-based search form that,
when submitted, performs a geo-location based search and returns all matching 
questions. On the backend this is accomplished by building a custom search
index and leveraging the built-in geo-location *Search API* provided by Google
App Engine.

_APIs employed: Search (geo-location based search, custom index), NDB Datastore._


**(Prospective) Location-based Question Search**

*Prospective Search* is an alpha-release feature provided by Google. It allows
for real-time document-based search. Prospective Search is configured by creating a subscription
and trying to match against the subscription query. When a match is found, 
a callback url is triggered through the App Engine Task Queue.

Within Megaphone, a subscription for Prospective Search is created when a user visits the *Profile* 
page and sets/updates a notification location and radius. The subscription is created for a duration
of 5 minutes. This duration was picked to enable ease and repeatability of testing. There is no technical 
limitation that prevents us from creating subscriptions that never expire. The created subscription 
notifies the user whenever a new question is posted within the notification radius. These steps result
in the creation of `ProspectiveUser` and `ProspectiveSubscription` objects.

When a new question is creted, an interim `NearbyQuestion` search document is created, but not saved to the 
datastore. Note that this document does not need to be stored in order for prospective search to work. This 
interim search document is created for each prospective user in the system. The document contains the coordinates of the 
user notification location and radius, along with the distance of the posted question to the notification point.
The subscription query tests whether the distance is within the notification radius; if the condition is satisfied, a match is found
resulting in a document being placed in the Task Queue. The appropriate handler for the task queue url sends a
notice to the matched prospective user.


Limitations of Propspective Search, however, complicated this implementation.
In particular, there are two issues at hand:

- location-based search is not available in the Prospective Search API. This
means that for each User-Question pair an intermediate object needs to be 
created to contain the distance from one to the other. This is expensive and slow.

- search queries are static (and match against static documents). That is, 
queries cannot be defined to take an input variable. This means that distances
must be recalculated each time a given user changes their search parameters.
Again, this requires the intermediate object mentioned above.


_APIs employed: Prospective Search, NDB Datastore._


**Real-time Notifications**

Using the *Channels API*  and the *Deferred* library, Megaphone posts 
notifications about certain events:

- Users are notified about new questions matching Prospective Search.
- Users are notified of new answers to their questions.

In both cases, JavaScript parses a JSON payload sent over a channel and
performs the necessary DOM manipualtions client-side to inform the user of the
event. Generally, notifications about new questions include a URL to the question,
whereas notifications about new answers trigger an AJAX fetch of the answer,
which is then inserted into the DOM using a custom animation.

_APIs employed: Channel, Deferred Tasks._


**Other**

- Memcached was used sparingly (within `views.py`) as a proof-of-concept. See
the methods prefixed with `@cache.cached`.


## Additional Application Usage Instructions

As mentioned in the [Application Overview](https://github.com/dfcarney/ece1779/tree/master/project-2#application-overview),
there are several main views that a logged-in user can access.

### Nearby Activity

![Nearby Activity](https://raw.githubusercontent.com/dfcarney/ece1779/master/project-2/doc/nearby%20activity.png)

This page shows the following:

- **Notices**: Channel API notifications that are handled via JavaScript. Current 
notification types are limited to (new) questions matching the user's Prospective
Search criteria (configured on their Profile page).

- **Nearby Questions**:
    - A search interface: for performing location-based searches for questions.
    - A list of search results.
    - A map, showing the locations of search results.

Clicking on the 'Content' of a particular question brings you to its 
own [Question Page](https://github.com/dfcarney/ece1779/tree/master/project-2#question-page). 
Clicking on '(open)' opens a map that shows the question's location.

### My Activity

![My Activity](https://raw.githubusercontent.com/dfcarney/ece1779/master/project-2/doc/my%20activity.png)

This page is nearly identical to [Nearby Activity](https://github.com/dfcarney/ece1779/tree/master/project-2#nearby-activity)
with the exception that its content (including Notices) limited to the user's own questions. In particular, Notices
only shows notifications for new answers to the user's questions.

### Profile

![Profile](https://raw.githubusercontent.com/dfcarney/ece1779/master/project-2/doc/profile.png)

On the Profile page a logged-in user can configure the search area to be used
in Prospective Search (i.e. for notifications about new questions).

### Question Page

![Question Page](https://raw.githubusercontent.com/dfcarney/ece1779/master/project-2/doc/question%20page.png)

The Question Page (for a given question) lists any and all answers posted by users.
The owner of a question may additionally accept one of the answers. The Notices header
is a placeholder and (currently) unused (except as a trigger to initialize 
JavaScript routines). Users viewing their own question will have new answers 
automatically prepended to the list via an AJAX callback.

## Project Organization

The project takes its form from the Flask example project, located here: https://github.com/kamalgill/flask-appengine-template.
As such, it does not follow a model-view-controller (MVC) model. While this
could be done, it was deemed not required for a project of this small size.

For a thorough introduction to Flask, see http://flask.pocoo.org/docs/0.10/

Files that saw a lot of changes during the development of Megaphone include the 
following:

- [`views.py`](https://github.com/dfcarney/ece1779/blob/master/project-2/megaphone/application/views.py): for simplicity, all logic bridging the views and models lies herein.
- [`urls.py`](https://github.com/dfcarney/ece1779/blob/master/project-2/megaphone/application/urls.py): speficies URL endpoints and routing information.
- [`models.py`](https://github.com/dfcarney/ece1779/blob/master/project-2/megaphone/application/models.py): contains model definitions for Question, Answer, etc.
- [`forms.py`](https://github.com/dfcarney/ece1779/blob/master/project-2/megaphone/application/forms.py): specifies the various `WTForms` used in the project.

## Known Issues

- Channel API handling needs to be overhauled to better track created channels
and reuse tokens, as opposed to always creating new channels/tokens. Otherwise,
the Google App Engine free-tier quotas are quickly exceeded. In a production
application, this would instead translate to a waste of money.

- Prospective Search should be performed only for registered users within the prospective search notification area. 
The current implementation naively tries to match against all registered users in the system. In a production application,
this will quickly become a bottleneck. A better approach would be to first identify users within the prospective notification area,
and then match to see if the posted question is within a user's noification radius.

## Future Work

Some ideas for future work include the following:

- Make better use of [Memcache](https://cloud.google.com/appengine/docs/python/memcache/)

- Use MapReduce to iterate over all questions and answers, determine trending/popular ones, to help identify hot activity zones.

- Benchmark performance/load characteristics to expose bottlenecks

- Improve Search & Prospective Search features

- Multiple Prospective Search locations per user

- Add more features for a richer user experience

## Python Flask Resources

- http://flask.pocoo.org/docs/0.10/quickstart/
- http://blog.luisrei.com/articles/flaskrest.html
