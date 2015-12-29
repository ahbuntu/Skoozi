"""
models.py - App Engine datastore models
"""

from google.appengine.ext import ndb
from protorpc import messages


class AppUserModel(ndb.Model):
    user_id = ndb.StringProperty(required=True)
    avatar_name = ndb.StringProperty()


class QuestionModel(ndb.Model):
    """ Base Model to represent questions and answers that are posted on the site
        user asks Question """
    added_by = ndb.StructuredProperty(AppUserModel, required=True)
    content = ndb.StringProperty(indexed=True)
    timestamp = ndb.DateTimeProperty(required=True)
    location = ndb.GeoPtProperty(required=False, indexed=True)
    # TODO: determine what lambda is being used for over here
    # formatted_location = messages.ComputedProperty(lambda self: self.location_url())


class AnswerModel(ndb.Model):
    """ Base Model to represent questions and answers that are posted on the site
        user provides Answer """
    added_by = ndb.StructuredProperty(AppUserModel, required=True)
    content = ndb.StringProperty(indexed=True)
    timestamp = ndb.DateTimeProperty(required=True)
    location = ndb.GeoPtProperty(required=False, indexed=True)
    # for_question = ndb.StructuredProperty(Post)


class QuestionMessage(messages.Message):
    """Post that stores a question """
    id_urlsafe = messages.StringField(1, required=False)
    # app_user_id = messages.StringField(2, required=True)
    content = messages.StringField(2, required=True)
    timestamp_unix = messages.IntegerField(3, required=True)
    locationLat = messages.FloatField(4, required=True)
    locationLon = messages.FloatField(5, required=True)


class AnswerMessage(messages.Message):
    """ Post that stores an answer """
    id_urlsafe = messages.StringField(1, required=False)
    question_urlsafe = messages.StringField(2, required=True)
    # TODO: figure out if the email is really required
    app_user_id = messages.StringField(3, required=True)
    content = messages.StringField(4, required=True)
    timestamp_unix = messages.IntegerField(5, required=True)
    locationLat = messages.FloatField(6, required=True)
    locationLon = messages.FloatField(7, required=True)


class StatusResponse(messages.Message):
    status = messages.StringField(1)


class PostResponse(messages.Message):
    post_key = messages.StringField(1)


class QuestionMessageCollection(messages.Message):
    """ Collection of AnswerMessages """
    questions = messages.MessageField(QuestionMessage, 1, repeated=True)


class AnswerMessageCollection(messages.Message):
    """ Collection of AnswerMessages """
    answers = messages.MessageField(AnswerMessage, 1, repeated=True)

