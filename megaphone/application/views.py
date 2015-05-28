"""
views.py

URL route handlers

Note that any handler params must match the URL route params.
For example the *say_hello* handler, handling the URL route '/hello/<username>',
  must be passed *username* as the argument.

"""
from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.runtime import apiproxy_errors
from google.appengine.runtime.apiproxy_errors import CapabilityDisabledError

import logging, math, datetime

from flask import request, render_template, flash, url_for, redirect, json, jsonify

from lib.flask_cache import Cache

from application import app
from decorators import login_required, admin_required

from forms import QuestionForm, AnswerForm, QuestionSearchForm, ProspectiveUserForm

from google.appengine.api import search, prospective_search
from google.appengine.api import channel

# For background jobs
from google.appengine.ext import deferred
from google.appengine.runtime import DeadlineExceededError

from models import Question, Answer, ProspectiveUser, ProspectiveSubscription, NearbyQuestion

# Flask-Cache (configured to use App Engine Memcache API)
cache = Cache(app)


def home():
    """The main landing page."""
    user = users.get_current_user()
    if user:
        return redirect(url_for('list_questions_for_user'))
    else:
        return redirect(url_for('list_questions'))


# No auth required
def search_questions():
    """Basic search API for Questions"""
    # questions = []
    search_form = QuestionSearchForm()
    if not search_form.validate_on_submit():
        return redirect(url_for('list_questions'))

    # Build the search params and redirect
    latitude = search_form.latitude.data
    longitude = search_form.longitude.data
    radius = search_form.distance_in_km.data
    return redirect(url_for('list_questions', lat=latitude, lon=longitude, r=radius))


def warmup():
    """App Engine warmup handler
    See http://code.google.com/appengine/docs/python/config/appconfig.html#Warming_Requests

    """
    logging.getLogger().setLevel(logging.DEBUG)
    return ''


def get_questions():
    """returns the questions in JSON format"""
    lat = request.args.get('lat', 0, type=float)
    lon = request.args.get('lon', 0, type=float)
    radius = request.args.get('radius', 0, type=float)

    if lat == 0 and lon == 0 and radius == 0:
        questions = Question.all()
    else:
        radius_in_metres = float(radius) * 1000.0
        q = "distance(location, geopoint(%f, %f)) <= %f" % (float(lat), float(lon), float(radius_in_metres))

        # build the index if not already done
        if search.get_indexes().__len__() == 0:
            rebuild_question_search_index()

        index = search.Index(name="myQuestions")
        results = index.search(q)

        # TODO: replace this with a proper .query
        questions = [Question.get_by_id(long(r.doc_id)) for r in results]
        questions = filter(None, questions) # filter deleted questions
        if questions:
            questions = sorted(questions, key=lambda question: question.timestamp)

    dataset = []
    for question in questions:
        # This conversion can be performed using a custom JsonEncoder implementation,
        # but I didn't have much success. Some good links below -
        # http://stackoverflow.com/questions/1531501/json-serialization-of-google-app-engine-models
        # https://gist.github.com/erichiggins/8969259
        # https://gist.github.com/bengrunfeld/062d0d8360667c47bc5b
        details = {'key': question.key.id(),
                   'added_by': question.added_by.nickname(),
                   'content': question.content,
                   'timestamp': question.timestamp.strftime('%m-%d-%y'),
                   'location': {'lat': question.location.lat,
                                'lon': question.location.lon}
                   }
        dataset.append(details)

    return jsonify(result=dataset)

@cache.cached(timeout=5)
def list_questions():
    """Lists all questions posted on the site - available to anonymous users"""
    form = QuestionForm()
    search_form = QuestionSearchForm()
    user = users.get_current_user()
    login_url = users.create_login_url(url_for('home'))

    query_string = request.query_string
    latitude = request.args.get('lat')
    longitude = request.args.get('lon')
    radius = request.args.get('r')

    # If searching w/ params (GET)
    if request.method == 'GET' and all(v is not None for v in (latitude, longitude, radius)):
        radius_in_metres = float(radius) * 1000.0
        q = "distance(location, geopoint(%f, %f)) <= %f" % (float(latitude), float(longitude), float(radius_in_metres))

        # build the index if not already done
        if search.get_indexes().__len__() == 0:
            rebuild_question_search_index()

        index = search.Index(name="myQuestions")
        results = index.search(q)

        # TODO: replace this with a proper .query
        questions = [Question.get_by_id(long(r.doc_id)) for r in results]
        questions = filter(None, questions) # filter deleted questions
        if questions:
            questions = sorted(questions, key=lambda question: question.timestamp)

        search_form.latitude.data = float(latitude)
        search_form.longitude.data = float(longitude)
        search_form.distance_in_km.data = radius_in_metres/1000.0
    else:
        questions = Question.all()

    channel_token = None
    if (user):
        channel_token = safe_channel_create(user_channel_id(user))
    return render_template('list_questions.html', questions=questions, form=form, user=user, login_url=login_url, search_form=search_form, channel_token=channel_token)


@login_required
def user_profile():
    """Displays the user profile page"""
    user = users.get_current_user()
    question_count = Question.count_for(user)
    answer_count = Answer.count_for(user)
    form = ProspectiveUserForm()
    all_prospective_users = ProspectiveUser.get_for(user)
    prospective_user = all_prospective_users.get()

    if request.method == 'POST':
        if prospective_user is None:
            prospective_user = ProspectiveUser (
                login = user,
                origin_location = get_location(form.origin_location.data),
                notification_radius_in_km = form.notification_radius_in_km.data,
                screen_name = form.screen_name.data
            )
        else:
            prospective_user.origin_location = get_location(form.origin_location.data)
            prospective_user.notification_radius_in_km = form.notification_radius_in_km.data
            prospective_user.screen_name = form.screen_name.data
        try:
            prospective_user.put()
            subscribe_user_for_nearby_questions(prospective_user.key.id())
            flash(u'Home location successfully saved.', 'success')

            return redirect(url_for('user_profile'))
        except CapabilityDisabledError:
            flash(u'App Engine Datastore is currently in read-only mode.', 'info')
            return redirect(url_for('user_profile'))

    return render_template('user_profile.html', user=user, prospective_user=prospective_user,
                           question_count=question_count, answer_count=answer_count, form=form)


@login_required
def list_questions_for_user():
    """Lists all questions posted by a user"""

    form = QuestionForm()
    search_form = QuestionSearchForm()
    user = users.get_current_user()
    login_url = users.create_login_url(url_for('home'))

    query_string = request.query_string
    latitude = request.args.get('lat')
    longitude = request.args.get('lon')
    radius = request.args.get('r')

    # If searching w/ params (GET)
    if request.method == 'GET' and all(v is not None for v in (latitude, longitude, radius)):
        q = "distance(location, geopoint(%f, %f)) <= %f" % (float(latitude), float(longitude), float(radius))
        index = search.Index(name="myQuestions")
        results = index.search(q)

        # TODO: replace this with a proper .query
        questions = [Question.get_by_id(long(r.doc_id)) for r in results]
        questions = filter(None, questions) # filter deleted questions
        if questions:
            questions = sorted(questions, key=lambda question: question.timestamp)
    else:
        questions = Question.all_for(user)

    channel_token = safe_channel_create(all_user_questions_answers_channel_id(user))
    return render_template('list_questions_for_user.html', questions=questions, form=form, user=user, login_url=login_url, search_form=search_form, channel_token=channel_token)


@login_required
def new_question():
    """Creates a new question"""
    form = QuestionForm()
    if request.method == 'POST' and form.validate_on_submit():
        question = Question(
            content=form.content.data,
            added_by=users.get_current_user(),
            location=get_location(form.location.data)
        )
        try:
            question.put()
            question_id = question.key.id()

            create_nearby_question(question_id)

            flash(u'Question %s successfully saved.' % question_id, 'success')
            add_question_to_search_index(question)


            return redirect(url_for('list_questions_for_user'))
        except CapabilityDisabledError:
            flash(u'App Engine Datastore is currently in read-only mode.', 'info')
            return redirect(url_for('list_questions_for_user'))
    else:
        flash_errors(form)
        return redirect(url_for('list_questions_for_user'))


def flash_errors(form):
    """Generates flash context for nice error display."""
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ))


def get_location(coords):
    """Returns a NDB GeoPt from coordinates."""
    return ndb.GeoPt(coords)


def add_question_to_search_index(question):
    """Build a custom search index for geo-based searched."""
    # FIXME: is this really necessary? Perhaps the Search API can infer this and built it automatically.
    index = search.Index(name="myQuestions")
    question_id = question.key.id()
    document = search.Document(
        doc_id=unicode(question_id),  # optional
        fields=[
            # search.TextField(name='customer', value='Joe Jackson'),
            # search.HtmlField(name='comment', value='this is <em>marked up</em> text'),
            # search.NumberField(name='number_of_visits', value=7),
            search.DateField(name='timestamp', value=question.timestamp),
            search.GeoField(name='location', value=search.GeoPoint(question.location.lat, question.location.lon))
            ])
    index.put_async(document)


def remove_question_from_search_index(question):
    """Remove a question from the geo-search index."""
    index = search.Index(name="myQuestions")
    question_id = question.key.id()
    doc_id = unicode(question_id)
    index.delete_async(doc_id)


@login_required
def edit_question(question_id):
    """Edit a question."""
    question = Question.get_by_id(question_id)
    form = QuestionForm(obj=question)
    user = users.get_current_user()
    if request.method == "POST":
        if form.validate_on_submit():
            question.content=form.data.get('content')
            question.location=form.data.get('location')
            question.put()
            flash(u'Question %s successfully modified.' % question_id, 'success')
            return redirect(url_for('list_questions_for_user'))
    return render_template('edit_question.html', question=question, form=form, user=user)


@login_required
def delete_question(question_id):
    """Delete a question."""
    question = Question.get_by_id(question_id)
    if request.method == "POST":
        try:
            remove_question_from_search_index(question)
            question.key.delete()
            flash(u'Question %s successfully deleted.' % question_id, 'success')
            return redirect(url_for('list_questions_for_user'))
        except CapabilityDisabledError:
            flash(u'App Engine Datastore is currently in read-only mode.', 'info')
            return redirect(url_for('list_questions_for_user'))


@login_required
def answers_for_question(question_id):
    """Provides a listing of the question and all of its associated answers."""
    question = Question.get_by_id(question_id)
    user = users.get_current_user()
    answerform = AnswerForm()
    answers = Answer.answers_for(question)
    accepted_answer = None
    if question.accepted_answer_key:
        accepted_answer = question.accepted_answer_key.get()

    # If the user owns the question then register for Channel notifications
    channel_token = None
    if (question.added_by == user):
        channel_id = question_answers_channel_id(user, question)
        channel_token = safe_channel_create(channel_id)

    return render_template('answers_for_question.html', answers=answers, question=question, user=user, form=answerform, channel_token=channel_token, accepted_answer=accepted_answer)


def safe_channel_create(channel_id):
    """Creates a Channel token; handles OverQuotaError exceptions."""
    try:
        channel_token = channel.create_channel(channel_id)
    except apiproxy_errors.OverQuotaError, message:
        # Log the error.
        logging.error(message)
        channel_token = None
    finally:
        return channel_token


@login_required
def answer(safe_answer_key):
    """Provides a single answer. Used for AJAX calls."""
    rev_key = ndb.Key(urlsafe=safe_answer_key)
    answer = rev_key.get()
    question_id = answer.key.parent().id()
    question = Question.get_by_id(question_id)
    return render_template('includes/answer.html', answer=answer, question=question)


@login_required
def new_answer(question_id):
    """Create a new answer corresponding to a question."""
    question = Question.get_by_id(question_id)
    answerform = AnswerForm()
    if request.method == "POST" and answerform.validate_on_submit():
        answer = Answer(
            content=answerform.content.data,
            added_by=users.get_current_user(),
            location=get_location(answerform.location.data),
            for_question=question,
            parent=question.key
        )
        try:
            answer.put()
            notify_new_answer(answer)
            answer_id = answer.key.id()

            flash(u'Answer %s successfully saved.' % answer_id, 'success')
            return redirect(url_for('answers_for_question', question_id=question_id))
        except CapabilityDisabledError:
            flash(u'App Engine Datastore is currently in read-only mode.', 'info')
            return redirect(url_for('answers_for_question', question_id=question_id))

    return render_template('new_answer.html', question=question, form=answerform)


@login_required
def accept_answer(safe_answer_key):
    """Accept the answer for a question."""

    rev_key = ndb.Key(urlsafe=safe_answer_key)
    answer = rev_key.get()
    question_id = answer.key.parent().id()
    question = Question.get_by_id(question_id)

    # questionform = QuestionForm(obj=question)
    accepted_answer=None
    if request.method == "POST":
        # if questionform.validate_on_submit():
        question.accepted_answer_key=answer.key
        accepted_answer=answer
        question.put()
        flash(u'Answer %s successfully accepted.' % question_id, 'success')
    elif question.accepted_answer_key:
        accepted_answer=question.accepted_answer_key.get()

    return redirect(url_for('answers_for_question', question_id=question_id, accepted_answer=accepted_answer))


# @admin_required
# FIXME: normal users shouldn't be able to execute this
def rebuild_question_search_index():
    """Used to generate/build the geo-search index."""
    questions = Question.all()
    [add_question_to_search_index(q) for q in questions]
    return redirect(url_for('list_questions'))


def authenticate():
    """Force the user to authenticate, if not already done."""
    user = users.get_current_user()
    if user:
        login_url = users.create_login_url(url_for('home'))
        logout_url = users.create_logout_url(login_url)
        return redirect(logout_url)
    else:
        return redirect(url_for('home'))


def login():
    """Force the user to login, if not already done."""
    user = users.get_current_user()
    if user:
        return redirect('/')
    else:
        login_url = users.create_login_url(url_for('home'))
        return redirect(login_url)


def list_subscriptions():
    """List all subscriptions."""
    subscriptions = prospective_search.list_subscriptions(
        NearbyQuestion
    )
    return render_template('list_subscriptions.html', subscriptions=subscriptions)


def match_prospective_search():
    """Callback on prospective search match."""
    if request.method == "POST":
        logging.info("received a match")
        webapp2Request = request.form
        nearby_question = prospective_search.get_document(webapp2Request)
        prospective_user = ProspectiveUser.get_by_id(nearby_question.for_prospective_user_id)
        question = Question.get_by_id(nearby_question.for_question_id)

        notify_new_question(prospective_user.login, question)
    return '', 200


def deg2rad(deg):
    """Helper to convert degrees to radians."""
    return deg * (math.pi/180)


def get_location_distance_in_km(lat1, lon1, lat2, lon2):
    """Get the geo-spatial distance between two lat/long pairs."""
    earth_radius = 6371 # Radius of the earth in km
    d_lat = deg2rad(lat2 - lat1)
    d_lon = deg2rad(lon2 - lon1)
    a = math.sin(d_lat/2) * math.sin(d_lat/2) + math.cos(deg2rad(lat1)) * math.cos(deg2rad(lat2)) * math.sin(d_lon/2) * math.sin(d_lon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = earth_radius * c # Distance in km
    return d


# Why do we need to create a NearbyQuestion for each ProspectiveUser/Question combo? It's obviously inefficient.
#
# Why not:
# - Questions are the documents being matched against
# - Each ProspectiveUser has a subscription (query) that matches against (new) Questions in a given radius
# - New question triggers Channel notification based on ID of ProspectiveUser
#
# Problem is that a query is static and doesn't perform any calculations/joins with other objects.
# So, if we want to search by distance to X then we have to calculate the distance for each Question
# beforehand and define a query that matches on that. This, of course, is ridiculous...but it's part
# of an experiment with Prospective Search.
def create_nearby_question(question_id):
    """Workaround for Prospective Searchs shortcomings; we need to create 
    NearbyQuestion objects for each User/Question pair."""
    prospective_users = ProspectiveUser.all()
    question = Question.get_by_id(question_id)
    for user_to_test in prospective_users:

        if user_to_test.login == question.added_by:
            continue # No need to create a search for your own questions

        # create a new document and subscribe to it
        distance_to_origin = get_location_distance_in_km(user_to_test.origin_location.lat,
                                                         user_to_test.origin_location.lon,
                                                         question.location.lat,
                                                         question.location.lon)
        nearby_prospective_question = NearbyQuestion(
            for_prospective_user_id=user_to_test.key.id(),
            for_question_id=question_id,
            origin_latitude=user_to_test.origin_location.lat,
            origin_longitude=user_to_test.origin_location.lon,
            origin_radius=user_to_test.notification_radius_in_km,
            origin_distance_in_km=distance_to_origin
        )

        # TODO: (potentially) only required for debugging purposes. Prospective_search.match might not required a saved entity.
        # nearby_prospective_question.put()

        # "Documents are assigned to a particular topic when calling match()"
        prospective_search.match(
            nearby_prospective_question
        )


def subscribe_user_for_nearby_questions(prospective_user_id):
    """Create new subscriptions for the provided question and user."""
    active_subscriptions = ProspectiveSubscription.get_for(prospective_user_id)
    sub = active_subscriptions.get()
    if sub is None:
        sub = ProspectiveSubscription(
            prospective_user_id=prospective_user_id
        )
        sub.put()

    prospective_user = ProspectiveUser.get_by_id(prospective_user_id)
    # nearby_question = NearbyQuestion.get_by_id(nearby_question_id)
    # query = 'origin_latitude = {:f} AND origin_longitude = {:f} AND origin_distance_in_km < {:d}'\
    #     .format(prospective_user.origin_location.lat, prospective_user.origin_location.lon, prospective_user.notification_radius_in_km)

    query = 'origin_distance_in_km < {:d}'.format(prospective_user.notification_radius_in_km)

    # "Topics are not defined as a separate step; instead, topics are created as a side effect of the subscribe() call."
    prospective_search.subscribe(
        NearbyQuestion,
        query,
        str(sub.key.id()),
        lease_duration_sec=300
    )


#####################
# Channel API Stuff #
#####################


def notify_new_question(user, question):
    """Notify relevant subscribers to a new question."""
    question_id = question.key.id()
    title = (question.content[:20] + '...') if len(question.content) > 20 else question.content
    url = url_for('answers_for_question', question_id=str(question_id))
    message = {'type': 'new_question',
               'question_id': question_id,
               'url': url,
               'title': title,
               'msg': "A new question was posted ('" + title + "'). Click <a href='" + url + "'>here</a> to view it."
               }

    # For now, only broadcast to the specific user; otherwise we risk
    # duplicate notifications if this method gets called in succession

    channel_id = user_channel_id(user)
    deferred.defer(channel_send_message, channel_id, message, _countdown=2)


def notify_new_answer(answer):
    """Notify relevant subscribers to a new answer."""
    question = answer.key.parent().get()
    question_id = question.key.id()
    title = (question.content[:20] + '...') if len(question.content) > 20 else question.content

    safe_answer_key = answer.key.urlsafe()

    load_answer_ajax_url = url_for('answer', safe_answer_key=safe_answer_key)
    goto_answer_url = url_for('answers_for_question', question_id=str(question_id))

    message = {'type': 'new_answer',
               'url': load_answer_ajax_url,
               'msg': "The question ('" + title + "') received a new answer. Click <a href='" + goto_answer_url + "'>here</a> to view it."
               }

    # Broadcast to the owner of the question, unless they answered it.
    if (question.added_by != answer.added_by):
        logging.info('[CHANNEL] Sending notifications about new answer: ' + str(answer.key.id()))

        channel_id = question_answers_channel_id(question.added_by, question)
        deferred.defer(channel_send_message, channel_id, message, _countdown=1)

        channel_id = all_user_questions_answers_channel_id(question.added_by)
        deferred.defer(channel_send_message, channel_id, message, _countdown=2)

        channel_id = user_channel_id(question.added_by)
        deferred.defer(channel_send_message, channel_id, message, _countdown=3)
    else:
        logging.info('[CHANNEL] Question answered by owner. Skipping notifications.')


def channel_send_message(channel_id, message):
    """Send a message to a given Channel."""
    tries = 1
    channel_token = safe_channel_create(channel_id)
    logging.info('[CHANNEL] starting channel_send_message to channel: ' + str(channel_id))
    message_json = json.dumps(message)

    for attempt in range(tries):
        # message = 'this is message number: ' + str(attempt)
        channel.send_message(channel_id, message_json)
        logging.info('[CHANNEL] just sent to: ' + str(channel_id) + '(' + message_json + ')')
        logging.info(channel_token)


def channel_connected():
    """Channel API callback (from JS client) when connection occurs."""
    channel = request.form['from']
    logging.info('user connected to: ' + str(channel))
    # TODO: use this to maintain a list of active channels
    return '', 200


def channel_disconnected():
    """Channel API callback (from JS client) when disconnection occurs."""
    channel = request.form['from']
    logging.info('user disconnected from: ' + str(channel))
    # TODO: use this to maintain a list of active channels
    return '', 200


# Channels don't support fan-out (and you can only have one active per page),
# but we have multiple ones defined for different contexts. After some
# experimentation it probably makes a lot more sense to have just a single
# channel per user and a JavaScript service that interprets and handles
# different message payloads accordingly.


def all_user_questions_answers_channel_id(user):
    return 'answers-' + str(user.user_id())


def question_answers_channel_id(user, question):
    return str(user.user_id()) + str(question.key.id())


def user_channel_id(user):
    return str(user.user_id())
