"""Hello World API implemented using Google Cloud Endpoints.

Defined here are the ProtoRPC messages needed to define Schemas for methods
as well as those methods defined in an API.
"""

import endpoints
import logging
import calendar, time
# from application import helpers
# from application import models
from core.models import Greeting, GreetingCollection
from core.models import AppUserModel, QuestionModel, QuestionMessage, QuestionMessageCollection
from core.models import AnswerModel, AnswerMessage, AnswerMessageCollection, PostResponse, ResetResponse
from datetime import datetime

from protorpc import messages
from protorpc import message_types
from protorpc import remote

from google.appengine.ext import ndb
from google.appengine.api import users, search, oauth

# https://apis-explorer.appspot.com/apis-explorer/?base=http%3A%2F%2Flocalhost%3A8282%2F_ah%2Fapi#p/skooziqna/v0.1/
package = 'Skoozi'
TAG = 'main.py'
ALL_QUESTIONS_INDEX = 'all_questions'

RAISE_UNAUTHORIZED = True
USER_INFO_SCOPE = 'https://www.googleapis.com/auth/userinfo.email'
WEB_CLIENT_ID = '26298710398-8jbuih8cj38ihi87bsloqkvur2mfut11.apps.googleusercontent.com'
ANDROID_CLIENT_ID = '26298710398-7s5ldlh5s8p0e4njp6hq6i94n8h70tri.apps.googleusercontent.com'
IOS_CLIENT_ID = 'fixme_when_ios_built'
ANDROID_AUDIENCE = WEB_CLIENT_ID

STORED_GREETINGS = GreetingCollection(items=[
    Greeting(message='hello world!'),
    Greeting(message='goodbye world!'),
    Greeting(message='good job')
])


def add_question_to_search_index(question):
    """Build a custom search index for geo-based searched."""
    index = search.Index(name=ALL_QUESTIONS_INDEX)
    document = search.Document(
        doc_id=unicode(question.key.id()),  # builds relationship between Question model and Question search document
        fields=[
            # search.HtmlField(name='comment', value='this is <em>marked up</em> text'),
            # search.NumberField(name='number_of_visits', value=7),
            # search.TextField(name='customer', value='Joe Jackson'), # might be needed in the future to enable question title searching
            search.DateField(name='timestamp', value=question.timestamp),  #watch out - no time information in search index
            search.GeoField(name='location', value=search.GeoPoint(question.location.lat, question.location.lon))
            ])

    # Index the document.
    try:
        index.put(document)
        logging.info("{}: added search document for Question key {}".format(TAG, question.key))
    except search.PutError, e:
        result = e.results[0]
        if result.code == search.OperationResult.TRANSIENT_ERROR:
            # possibly retry indexing result.object_id
            logging.error("{}: error while adding to search index, with result code {}".format(TAG, result.code))
    except search.Error, e:
        # log the failure
        logging.exception(e)


def add_question_to_search_index_by_key(question_key):
    """Build a custom search index for geo-based searched."""
    index = search.Index(name=ALL_QUESTIONS_INDEX)
    question = question_key.get()
    document = search.Document(
        doc_id=unicode(question_key.id()),  # builds relationship between Question model and Question search document
        fields=[
            # search.HtmlField(name='comment', value='this is <em>marked up</em> text'),
            # search.NumberField(name='number_of_visits', value=7),
            # search.TextField(name='content', value=question.content), # in future to enable question content searching
            search.DateField(name='timestamp', value=question.timestamp),
            search.GeoField(name='location', value=search.GeoPoint(question.location.lat, question.location.lon))
            ])
    try:
        index.put_async(document)
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
    questions = QuestionModel.query()
    [add_question_to_search_index(q) for q in questions]


# TODO: this functionality shoudl be resitricted to admin user(s) using oauth
def prune_question_search_index():
    """Delete all the docs in the given index."""
    doc_index = search.Index(name=ALL_QUESTIONS_INDEX)
    # looping because get_range by default returns up to 100 documents at a time
    while True:
        # Get a list of documents populating only the doc_id field and extract the ids.
        document_ids = [document.doc_id for document in doc_index.get_range(ids_only=True)]
        if not document_ids:
            break
        # Delete the documents for the given ids from the Index.
        doc_index.delete(document_ids)


def is_user_authorized():
    # https://cloud.google.com/appengine/docs/python/endpoints/auth
    current_user = endpoints.get_current_user()
    if current_user is None:
        return False
    return True


def authenticate_user():
    """Quite possible that endpoints.get_current_user() may perform the authentication being performed here
    Ref: https://cloud.google.com/appengine/docs/python/endpoints/auth -Adding a user check to methods- """

    scope = 'https://www.googleapis.com/auth/userinfo.email'
    logging.info('\noauth.get_current_user(%s)' % repr(scope))
    try:
        user = oauth.get_current_user(scope)
        allowed_clients = ['407408718192.apps.googleusercontent.com'] # list your client ids here
        token_audience = oauth.get_client_id(scope)
        if token_audience not in allowed_clients:
            raise oauth.OAuthRequestError('audience of token \'%s\' is not in allowed list (%s)'
                                          % (token_audience, allowed_clients))

        logging.info(' = %s\n' % user)
        logging.info('- auth_domain = %s\n' % user.auth_domain())
        logging.info('- email       = %s\n' % user.email())
        logging.info('- nickname    = %s\n' % user.nickname())
        logging.info('- user_id     = %s\n' % user.user_id())
    except oauth.OAuthRequestError, e:
        # # self.response.set_status(401)
        # # self.response.write(' -> %s %s\n' % (e.__class__.__name__, e.message))
        # logging.warn(traceback.format_exc())
        logging.error(e.message)


def authenticate_admin_user():
    """returns true if admin. does not verify allowed clients membership"""
    if oauth.is_current_user_admin(endpoints.EMAIL_SCOPE):
        return True
    return False


@endpoints.api(name='skooziqna', version='v0.1',
               # endpoints.API_EXPLORER_CLIENT_ID needed for testing against API Explorer in production.
               allowed_client_ids=[WEB_CLIENT_ID, ANDROID_CLIENT_ID, IOS_CLIENT_ID, endpoints.API_EXPLORER_CLIENT_ID],
               audiences=[ANDROID_AUDIENCE], scopes=[endpoints.EMAIL_SCOPE])
class SkooziQnAApi(remote.Service):
    """SkooziQnAAPI v0.1"""

    @endpoints.method(message_types.VoidMessage, ResetResponse, path='resetindex', http_method='GET',
                      name='admin.resetindex')
    def reset_search_index(self, unused_request):
        if authenticate_admin_user():
            prune_question_search_index()
        else:
            message = 'User "%s" does not have admin rights.' % oauth.get_current_user(USER_INFO_SCOPE).nickname()
            raise endpoints.UnauthorizedException(message)
        return ResetResponse(reset_status='SUCCESS')

    @endpoints.method(message_types.VoidMessage, GreetingCollection, path='hellogreeting', http_method='GET',
                      name='greetings.listGreeting')
    def greetings_list(self, unused_request):
        return STORED_GREETINGS

    ID_RESOURCE = endpoints.ResourceContainer(
        message_types.VoidMessage,
        id=messages.IntegerField(1, variant=messages.Variant.INT32))

    @endpoints.method(ID_RESOURCE, Greeting, path='hellogreeting/{id}', http_method='GET',
                      name='greetings.getGreeting')
    def greeting_get(self, request):
        try:
            # test = helpers.api_get_questions()
            return STORED_GREETINGS.items[request.id]
        except (IndexError, TypeError):
            raise endpoints.NotFoundException('Greeting %s not found.' %
                                        (request.id,))

    @endpoints.method(QuestionMessage, PostResponse, path='question/insert', http_method='POST',
                      name='question.insert')
    def question_insert(self, request):
        """Inserts the question to the datastore and makes it available for searching. Will also create user account
        if it doesn't exist"""

        current_user = endpoints.get_current_user()  # returns oauth authenticated user
        if current_user is not None:
            app_user = self.get_app_user()
            question = QuestionModel(
                added_by=app_user,
                content=request.content,
                # http://stackoverflow.com/questions/1697815/how-do-you-convert-a-python-time-struct-time-object-into-a-datetime-object
                timestamp=datetime.fromtimestamp(request.timestamp_unix),
                location=ndb.GeoPt(request.locationLat, request.locationLon))
            question_key = question.put()
            add_question_to_search_index_by_key(question_key)
            response = PostResponse(post_key=question_key.urlsafe())
            return response
        else:
            raise endpoints.UnauthorizedException('Invalid token.')

    @staticmethod
    def get_app_user():
        # need to use oauth.get_current_user since endpoints.get_current_user doesn't return user_id
        oauth_user_id = oauth.get_current_user(USER_INFO_SCOPE).user_id()
        model_users = AppUserModel.query(AppUserModel.user_id == oauth_user_id).fetch()
        if len(model_users) == 0:
            model_user = AppUserModel(user_id=oauth_user_id)
            model_user.put_async()
            return model_user
        elif len(model_users) == 1:
            return model_users[0]
        else:
            logging.info("Retrieved more than 1 single app user model")
            logging.debug("oauth_user_id: {} is repeated in app user model".format(oauth_user_id))
            raise endpoints.InternalServerErrorException

    NEARBY_ID_RESOURCE = endpoints.ResourceContainer(
        message_types.VoidMessage,
        lat=messages.FloatField(1),
        lon=messages.FloatField(2),
        radius_km=messages.FloatField(3))

    @endpoints.method(NEARBY_ID_RESOURCE, QuestionMessageCollection, path='questions/list', http_method='GET',
                      name='questions.list')
    def questions_list(self, request):
        query_lat = float(request.lat) if request.lat else 0
        query_lon = float(request.lon) if request.lon else 0
        query_radius = float(request.radius_km * 1000.0) if request.radius_km else 0

        if query_lat == 0 or query_lon == 0 or query_radius == 0:
            raise endpoints.BadRequestException("One of the required parameters (lat, lon, radius) is undefined")

        query_string = "distance(location, geopoint(%f, %f)) <= %f" % (query_lat, query_lon, query_radius)

        # build the index if not already done
        if search.get_indexes().__len__() == 0:
            rebuild_question_search_index()
        index = search.Index(name=ALL_QUESTIONS_INDEX)
        search_results = index.search(query_string)

        search_questions = []
        for search_item in search_results:
            retrieved_question = QuestionModel.get_by_id(long(search_item.doc_id))
            # condition accounts for the case when the search index is stale since it contains references to questions
            # no longer in the datastore
            if retrieved_question is None:
                logging.info("{} index has extra documents".format(ALL_QUESTIONS_INDEX))
                logging.debug("Following search document was not found in Question model")
                logging.debug(retrieved_question)
                # TODO: very aggressive strategy - need to find better way of pruning - maybe async task queue
                prune_question_search_index()
            else:
                search_questions.append(retrieved_question)
        # questions = [QuestionModel.get_by_id(long(r.doc_id)) for r in results]

        # for question in search_questions:
        #     returned_questions.append(self.create_api_response_question(question))
        # returned_questions=[]
        # returned_questions.append(self.create_api_response_question(question) for question in search_questions)

        returned_questions = [self.create_api_response_question(question) for question in search_questions]

        return_list = QuestionMessageCollection(questions=returned_questions)
        return return_list

    @staticmethod
    def create_api_response_question(question):
        return QuestionMessage(
                id_urlsafe=question.key.urlsafe(),
                email=question.added_by.email(),
                content=question.content,
                timestamp_unix=int(time.mktime(question.timestamp.timetuple())),
                locationLat=question.location.lat,
                locationLon=question.location.lon
        )

    @endpoints.method(AnswerMessage, PostResponse, path='answer/insert', http_method='POST',
                      name='answer.insert')
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
        answer = AnswerModel(
            added_by = user,
            content = request.content,
            # http://stackoverflow.com/questions/1697815/how-do-you-convert-a-python-time-struct-time-object-into-a-datetime-object
            timestamp = datetime.fromtimestamp(request.timestamp_unix),
            location = ndb.GeoPt(request.locationLat, request.locationLon),
            parent = question_key
        )
        answer_key = answer.put()

        response = PostResponse(post_key=answer_key.urlsafe())
        return response

    Q_ID_RESOURCE = endpoints.ResourceContainer(
        message_types.VoidMessage,
        id=messages.StringField(1))

    @endpoints.method(Q_ID_RESOURCE, AnswerMessageCollection, path='answers_for_question', http_method='GET',
                      name='question.listAnswers')
    def question_answers_list(self, request):
        # question_key = ndb.Key(urlsafe = 'ag5kZXZ-c2tvb3ppLTk1OXIaCxINUXVlc3Rpb25Nb2RlbBiAgICAgOidCgw')
        question_key = ndb.Key(urlsafe = request.id)
        q_answers = AnswerModel.query(ancestor=question_key).fetch()
        a_list = []
        for answer in q_answers:
            answer_message = AnswerMessage(
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
        return_list = AnswerMessageCollection(answers=a_list)
        return return_list

application = endpoints.api_server([SkooziQnAApi])
# Generate Android client library
# python "C:\Program Files (x86)\Google\google_appengine\endpointscfg.py" get_client_lib java -bs gradle main.SkooziQnAApi