__author__ = 'ahmadul.hassan'

from flask import jsonify
from models import Question
from google.appengine.api import search

def api_add_question_to_search_index(question):
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

def api_rebuild_question_search_index():
    """Used to generate/build the geo-search index."""
    questions = Question.all()
    [api_add_question_to_search_index(q) for q in questions]
    # return redirect(url_for('list_questions'))

def api_get_questions(lat=0, lon=0, radius=0):
    """returns the questions in JSON format"""
    if lat == 0 and lon == 0 and radius == 0:
        questions = Question.all()
    else:
        radius_in_metres = float(radius) * 1000.0
        q = "distance(location, geopoint(%f, %f)) <= %f" % (float(lat), float(lon), float(radius_in_metres))

        # build the index if not already done
        if search.get_indexes().__len__() == 0:
            api_rebuild_question_search_index()

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
