"""Hello World API implemented using Google Cloud Endpoints.

Defined here are the ProtoRPC messages needed to define Schemas for methods
as well as those methods defined in an API.
"""

import endpoints
import logging
import calendar, time
# from application import helpers
# from application import models
from core import models
from datetime import datetime

from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.ext import ndb, db
from google.appengine.api import users, search

# https://apis-explorer.appspot.com/apis-explorer/?base=http%3A%2F%2Flocalhost%3A8282%2F_ah%2Fapi#p/skooziqna/v0.1/
package = 'Skoozi'
TAG = 'main.py'
RAISE_UNAUTHORIZED = False
ALL_QUESTIONS_INDEX = 'all_questions'


STORED_GREETINGS = models.GreetingCollection(items=[
    models.Greeting(message='hello world!'),
    models.Greeting(message='goodbye world!'),
    models.Greeting(message='good job')
])


def add_question_to_search_index(question_key):
    """Build a custom search index for geo-based searched."""
    index = search.Index(name=ALL_QUESTIONS_INDEX)
    question = question_key.get()
    document = search.Document(
        doc_id=unicode(question_key.id()),  # builds relationship between Question model and Question search document
        fields=[
            # search.HtmlField(name='comment', value='this is <em>marked up</em> text'),
            # search.NumberField(name='number_of_visits', value=7),
            # search.TextField(name='customer', value='Joe Jackson'), # might be needed in the future to enable question title searching
            search.DateField(name='timestamp', value=question.timestamp), # watch out - no time information in search index
            search.GeoField(name='location', value=search.GeoPoint(question.location.lat, question.location.lon))
            ])

    # Index the document.
    try:
        index.put(document)
        logging.info("{}: added search document for Question key {}".format(TAG, question_key))
    except search.PutError, e:
        result = e.results[0]
        if result.code == search.OperationResult.TRANSIENT_ERROR:
            # possibly retry indexing result.object_id
            logging.error("{}: error while adding to search index, with result code {}".format(TAG, result.code))
    except search.Error, e:
        # log the failure
        logging.exception(e)


# @admin_required
# FIXME: normal users shouldn't be able to execute this
def rebuild_question_search_index():
    """Used to generate/build the geo-search index."""

    logging.info("Rebuilding question search index")
    questions = models.QuestionModel.query()
    [add_question_to_search_index(q) for q in questions]

# TODO: this functionality shoudl be resitricted to admin user(s) using oauth
def reset_question_search_index():
    """Delete all the docs in the given index."""
    doc_index = search.Index(name=ALL_QUESTIONS_INDEX)

    # looping because get_range by default returns up to 100 documents at a time
    while True:
        # Get a list of documents populating only the doc_id field and extract the ids.
        document_ids = [document.doc_id
                        for document in doc_index.get_range(ids_only=True)]
        if not document_ids:
            break
        # Delete the documents for the given ids from the Index.
        doc_index.delete(document_ids)

@endpoints.api(name='skooziqna', version='v0.1')
class SkooziQnAApi(remote.Service):
    """SkooziQnAAPI v0.1"""

    @endpoints.method(message_types.VoidMessage, models.GreetingCollection,
                    path='hellogreeting', http_method='GET', name='greetings.listGreeting')
    def greetings_list(self, unused_request):
        return STORED_GREETINGS

    ID_RESOURCE = endpoints.ResourceContainer(
        message_types.VoidMessage,
        id=messages.IntegerField(1, variant=messages.Variant.INT32))

    @endpoints.method(ID_RESOURCE, models.Greeting,
                    path='hellogreeting/{id}', http_method='GET', name='greetings.getGreeting')
    def greeting_get(self, request):
        try:
            # test = helpers.api_get_questions()
            return STORED_GREETINGS.items[request.id]
        except (IndexError, TypeError):
            raise endpoints.NotFoundException('Greeting %s not found.' %
                                        (request.id,))


    @endpoints.method(models.QuestionMessage, models.PostResponse,
                    path='question/insert', http_method='POST', name='question.insert')
    def question_insert(self, request):
        # TODO: move this to a decorator maybe?
        # https://cloud.google.com/appengine/docs/python/endpoints/auth
        # ref section "Adding a user check to methods"
        # https://cloud.google.com/appengine/docs/python/users/userobjects
        # ASSUMPTION: only Google Accounts used for authenticaion
        current_user = endpoints.get_current_user()
        if RAISE_UNAUTHORIZED and current_user is None:
            raise endpoints.UnauthorizedException('Invalid token.')
        # TODO: need to figure out how to handle cases where Google Account is not present
        user = users.User(request.email)

        question = models.QuestionModel(
            added_by=user,
            content=request.content,
            # http://stackoverflow.com/questions/1697815/how-do-you-convert-a-python-time-struct-time-object-into-a-datetime-object
            timestamp=datetime.fromtimestamp(request.timestamp_unix),
            location=ndb.GeoPt(request.locationLat, request.locationLon)
        )
        question_key = question.put()
        add_question_to_search_index(question_key)
        response = models.PostResponse(post_key=question_key.urlsafe())
        # return STORED_GREETINGS.items[2]
        return response

    NEARBY_ID_RESOURCE = endpoints.ResourceContainer(
        message_types.VoidMessage,
        lat=messages.FloatField(1),
        lon=messages.FloatField(2),
        radius_km=messages.FloatField(3))


    @endpoints.method(NEARBY_ID_RESOURCE, models.QuestionMessageCollection,
                    path='questions/list', http_method='GET', name='questions.list')
    def questions_list(self, request):
        query_lat = float(request.lat) if request.lat else 0
        query_lon = float(request.lon) if request.lon else 0
        query_radius = float(request.radius_km * 1000.0) if request.radius_km else 50000.0 #default radius of 50km

        if (query_lat==0 or query_lon==0):
            # TODO: show all questions for Toronto
            query_string = "timestamp > 2013-3-13"
        else:
            query_string = "distance(location, geopoint(%f, %f)) <= %f" % (query_lat, query_lon, query_radius)

        # build the index if not already done
        if search.get_indexes().__len__() == 0:
            rebuild_question_search_index()

        search_questions = []
        index = search.Index(name=ALL_QUESTIONS_INDEX)
        search_results = index.search(query_string)
        for search_item in search_results:
            retrieved_question = models.QuestionModel.get_by_id(long(search_item.doc_id))
            if retrieved_question is None:
                logging.info("{} index has extra documents".format(ALL_QUESTIONS_INDEX))
                logging.debug("Following search document was not found in Question model")
                logging.debug(retrieved_question)
                # TODO: very aggressive strategy - need to find better way of pruning - maybe async task queue
                reset_question_search_index()
            else:
                search_questions.append(retrieved_question)
        # questions = [models.QuestionModel.get_by_id(long(r.doc_id)) for r in results]

        returned_questions = []
        for question in search_questions:
            question_message = models.QuestionMessage(
                id_urlsafe=question.key.urlsafe(),
                email=question.added_by.email(),
                content=question.content,
                timestamp_unix=int(time.mktime(question.timestamp.timetuple())),
                locationLat=question.location.lat,
                locationLon=question.location.lon
            )
            returned_questions.append(question_message)
        return_list = models.QuestionMessageCollection(questions=returned_questions)
        return return_list

    @endpoints.method(models.AnswerMessage, models.PostResponse,
                    path='answer/insert', http_method='POST', name='answer.insert')
    def answer_insert(self, request):
        # TODO: move this to a decorator maybe?
        # https://cloud.google.com/appengine/docs/python/endpoints/auth
        # ref section "Adding a user check to methods"
        # https://cloud.google.com/appengine/docs/python/users/userobjects
        # ASSUMPTION: only Google Accounts used for authenticaion
        current_user = endpoints.get_current_user()
        if RAISE_UNAUTHORIZED and current_user is None:
            raise endpoints.UnauthorizedException('Invalid token.')
        # TODO: need to figure out how to handle cases where Google Account is not present
        user = users.User(request.email)

        question_key = ndb.Key(urlsafe=request.question_urlsafe)
        answer = models.AnswerModel(
            added_by = user,
            content = request.content,
            # http://stackoverflow.com/questions/1697815/how-do-you-convert-a-python-time-struct-time-object-into-a-datetime-object
            timestamp = datetime.fromtimestamp(request.timestamp_unix),
            location = ndb.GeoPt(request.locationLat, request.locationLon),
            parent = question_key
        )
        answer_key = answer.put()

        response = models.PostResponse(post_key=answer_key.urlsafe())
        return response

    Q_ID_RESOURCE = endpoints.ResourceContainer(
        message_types.VoidMessage,
        id=messages.StringField(1))

    @endpoints.method(Q_ID_RESOURCE, models.AnswerMessageCollection,
                    path='answers_for_question', http_method='GET', name='question.listAnswers')
    def question_answers_list(self, request):
        # question_key = ndb.Key(urlsafe = 'ag5kZXZ-c2tvb3ppLTk1OXIaCxINUXVlc3Rpb25Nb2RlbBiAgICAgOidCgw')
        question_key = ndb.Key(urlsafe = request.id)
        q_answers = models.AnswerModel.query(ancestor=question_key).fetch()
        a_list = []
        for answer in q_answers:
            answer_message = models.AnswerMessage(
                id_urlsafe = answer.key.urlsafe(),
                question_urlsafe = question_key.urlsafe(),
                email = answer.added_by.email(),
                content = answer.content,
                # date_time_milis = time.mktime(datetimeobj.timetuple()) * 1000 + datetimeobj.microsecond / 1000
                timestamp_unix = int(time.mktime(answer.timestamp.timetuple())),
                locationLat = answer.location.lat,
                locationLon = answer.location.lon
            )
            a_list.append(answer_message)
        return_list = models.AnswerMessageCollection(answers=a_list)
        return return_list

application = endpoints.api_server([SkooziQnAApi])
# Generate Android client library
# python "C:\Program Files (x86)\Google\google_appengine\endpointscfg.py" get_client_lib java -bs gradle main.SkooziQnAApi