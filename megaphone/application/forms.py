"""
forms.py

Web forms based on Flask-WTForms

See: http://flask.pocoo.org/docs/patterns/wtforms/
     http://wtforms.simplecodes.com/

"""

from flaskext import wtf
from flaskext.wtf import validators
from wtforms.ext.appengine.ndb import model_form

from .models import Question, Answer, QuestionSearch, ProspectiveUser

class ClassicQuestionSearchForm(wtf.Form):
    latitude = wtf.DecimalField('Latitude',  validators=[validators.Required()])
    longitude = wtf.DecimalField('Longitude', validators=[validators.Required()])
    distance_in_km = wtf.DecimalField('Distance (km)',  validators=[validators.Required()])

QuestionSearchForm = model_form(QuestionSearch, wtf.Form, field_args={
    'latitude': dict(validators=[validators.Required()]),
    'longitude': dict(validators=[validators.Required()]),
    'distance_in_km': dict(validators=[validators.Required()]),
})

ProspectiveUserForm = model_form(ProspectiveUser, wtf.Form, field_args={
    'login': dict(validators=[validators.Required()]),
    'origin_location': dict(validators=[validators.Required()]),
    'notification_radius_in_km': dict(validators=[validators.Required()]),
    'screen_name': dict(validators=[validators.Required()]),
})


class QuestionForm(wtf.Form):
    content = wtf.TextAreaField('Content', validators=[validators.Required()])
    location = wtf.TextField('Location', validators=[validators.Required()])


class AnswerForm(wtf.Form):
    content = wtf.TextAreaField('Content', validators=[validators.Required()])
    location = wtf.TextField('Location', validators=[validators.Required()])

class PostForm(wtf.Form):
    content = wtf.TextAreaField('Content', validators=[validators.Required()])

# QuestionForm = model_form(Question, wtf.Form, field_args={
#     'content': dict(validators=[validators.Required()]),
#     'location': dict(validators=[validators.Required()]),
# })

