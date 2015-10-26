"""
models.py - App Engine datastore models
"""

from google.appengine.ext import ndb
from protorpc import messages

class QuestionModel(ndb.Model):
    """ Base Model to represent questions and answers that are posted on the site
        user asks Question """
    # TODO: fix this UserProperty issue
    # strongly recommend that you do not store a UserProperty, because it includes the email address along with the
    # user's unique ID. If a user changes their email address and you compare their old, stored User to the new User value,
    # they won't match. Instead, consider using the User user ID value as the user's stable unique identifier.
    # https://cloud.google.com/appengine/docs/python/users/userobjects
    added_by = ndb.UserProperty(required=True)
    content = ndb.StringProperty(indexed=True)
    timestamp = ndb.DateTimeProperty(required=True)
    location = ndb.GeoPtProperty(required=False, indexed=True)
    # TODO: determine what lambda is being used for over here
    # formatted_location = messages.ComputedProperty(lambda self: self.location_url())

class AnswerModel(ndb.Model):
    """ Base Model to represent questions and answers that are posted on the site
        user provides Answer """
    added_by = ndb.UserProperty(required=True)
    content = ndb.StringProperty(indexed=True)
    timestamp = ndb.DateTimeProperty(required=True)
    location = ndb.GeoPtProperty(required=False, indexed=True)
    # for_question = ndb.StructuredProperty(Post)

class QuestionMessage(messages.Message):
    """Post that stores a question """
    id_urlsafe = messages.StringField(1, required=False)
    # TODO: figure out if the email is really required
    email = messages.StringField(2, required=True)
    content = messages.StringField(3, required=True)
    timestamp_unix = messages.IntegerField(4, required=True)
    locationLat = messages.FloatField(5, required=True)
    locationLon = messages.FloatField(6, required=True)

class AnswerMessage(messages.Message):
    """ Post that stores an answer """
    id_urlsafe = messages.StringField(1, required=False)
    question_urlsafe = messages.StringField(2, required=True)
    # TODO: figure out if the email is really required
    email = messages.StringField(3, required=True)
    content = messages.StringField(4, required=True)
    timestamp_unix = messages.IntegerField(5, required=True)
    locationLat = messages.FloatField(6, required=True)
    locationLon = messages.FloatField(7, required=True)

class ResetResponse(messages.Message):
    reset_status = messages.StringField(1)

class PostResponse(messages.Message):
    post_key = messages.StringField(1)

class QuestionMessageCollection(messages.Message):
    """ Collection of AnswerMessages """
    questions = messages.MessageField(QuestionMessage, 1, repeated=True)

class AnswerMessageCollection(messages.Message):
    """ Collection of AnswerMessages """
    answers = messages.MessageField(AnswerMessage, 1, repeated=True)

class Greeting(messages.Message):
    """Greeting that stores a message."""
    message = messages.StringField(1)


class GreetingCollection(messages.Message):
    """Collection of Greetings."""
    items = messages.MessageField(Greeting, 1, repeated=True)


