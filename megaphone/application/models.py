"""
models.py

App Engine datastore models

"""


from google.appengine.ext import ndb, db


class Post(ndb.Model):
    """Base Model to represent questions and answers that are posted on the site"""
    added_by = ndb.UserProperty(required=True)
    content = ndb.StringProperty(indexed=True)
    timestamp = ndb.DateTimeProperty(auto_now_add=True)
    location = ndb.GeoPtProperty(required=False, indexed=True)
    formatted_location = ndb.ComputedProperty(lambda self: self.location_url())

    def location_url(self):
        if self.location is None:
            return ""
        else:
            lat = self.location.lat
            lon = self.location.lon
            return 'http://maps.google.com/maps?z=12&t=m&q=loc:' + str(lat) + '+' + str(lon)


class Answer(Post):
    """A User answers a Question"""
    for_question = ndb.StructuredProperty(Post)

    @classmethod
    def answers_for(self, question):
        return self.query(self.for_question == question).order(-self.timestamp) # oldest first

    @classmethod
    def all(self):
        return self.query()

    @classmethod
    def count_for(self, user):
        return self.query(self.added_by == user).count()

    @classmethod
    def can_be_deleted(self):
        return True  # TODO: return false if is an accepted_answer


class Question(Post):
    """A User asks a Question"""
    accepted_answer_key = ndb.KeyProperty(kind=Answer)# ndb.StructuredProperty(Answer)  # there can only be one!

    @classmethod
    def can_be_deleted(self):
        return True  # TODO: return false if is an accepted_answer

    @classmethod
    def all(self):
        return self.query().order(-self.timestamp) # newest first

    @classmethod
    def all_for(self, user):
        return self.query(self.added_by == user).order(-self.timestamp) # newest first

    @classmethod
    def count_for(self, user):
        return self.query(self.added_by == user).count()


class QuestionSearch(ndb.Model):
    latitude = ndb.FloatProperty(required=True)
    longitude = ndb.FloatProperty(required=True)
    distance_in_km = ndb.FloatProperty(required=True)


class ProspectiveUser(ndb.Model):
    """Model to store user preferences"""
    login = ndb.UserProperty(required=True)
    origin_location = ndb.GeoPtProperty(required=True, indexed=True)
    notification_radius_in_km = ndb.IntegerProperty(required=False)
    screen_name = ndb.StringProperty(required=False)

    @classmethod
    def get_for(self, user):
        return self.query(self.login == user)

    @classmethod
    def all(self):
        return self.query()


class ProspectiveSubscription(ndb.Model):
    """Provides information on a subscription for a question."""
    prospective_user_id = ndb.IntegerProperty(required=True)
    created = ndb.DateTimeProperty(required=True, auto_now=True)

    @classmethod
    def get_for(self, prospective_user_id):
        return self.query(self.prospective_user_id == prospective_user_id)

class NearbyQuestion(db.Model):
    """Represents distance of a post to the specified origin.
    Origin represents the origin_location of the ProspectiveUser"""
    for_prospective_user_id = db.IntegerProperty(required=True)
    for_question_id = db.IntegerProperty(required=True)
    origin_latitude = db.FloatProperty(required=True)
    origin_longitude = db.FloatProperty(required=True)
    origin_radius = db.IntegerProperty(required=True)
    origin_distance_in_km = db.FloatProperty(required=True)
