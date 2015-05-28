/**
 * Created by ahmadul.hassan on 2015-04-01.
 */

$().ready(function() {
    latParam = getParameterByName("lat");
    lonParam = getParameterByName("lon");
    if (latParam && lonParam) {
        findLatLonAddress(latParam, lonParam);
    } else {
        latParam = 0;
        lonParam = 0;
    }

    displayMap();
    //displayQuestionMarkers();
});

var map;
var centreMarker;
var latParam;
var lonParam;

function getParameterByName(name) {
    name = name.replace(/[\[]/, "\\[").replace(/[\]]/, "\\]");
    var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),
        parVals = regex.exec(location.search);
    return parVals === null ? "" : decodeURIComponent(parVals[1].replace(/\+/g, " "));
}

function displayMap() {
    var mapCanvas = document.getElementById('map-canvas');
    var defaultLoc = new google.maps.LatLng(43.7182713,-79.3777061); //Toronto coords from google maps
    var mapOptions = {
      center: defaultLoc,
      zoom: 11,
      mapTypeId: google.maps.MapTypeId.ROADMAP
    }
    map = new google.maps.Map(mapCanvas, mapOptions);
    //marker for search centre
    centreMarker = new google.maps.Marker({
        position: defaultLoc,
        icon: 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png',
        map: map,
        title: "Search Origin"
    });
    displayQuestionMarkers();

}
//google.maps.event.addDomListener(window, 'load', initialize);

function displayQuestionMarkers() {
    $.getJSON($SCRIPT_ROOT + '/_get_questions', {
        //values of 0 returns all questions
        lat: latParam,
        lon: lonParam,
        radius: $("#distance_in_km").val()
    }, function(data) {
        var questions = data.result;
        for (var idx in questions) {
            var questionMarkerLatLng = new google.maps.LatLng(questions[idx].location.lat,
                                                                questions[idx].location.lon);
            //alert(questions[idx].content);
            var marker = new google.maps.Marker({
                position: questionMarkerLatLng,
                map: map,
                title:questions[idx].content
            });
        }
        //var test = JSON.stringify(questions);
    });
}

function findAddressLatLng() {
    var inputAddress = $("#address_geolocation").val();
    if (!inputAddress) {
        alert("Please enter address.");
        return;
    }
    var geocoder = new google.maps.Geocoder();
    geocoder.geocode({
        "address": inputAddress
    }, function(results, status) {
        if (status == google.maps.GeocoderStatus.OK) {
            var markerLatLng = (results[0].geometry.location); //LatLng
            centreMarker.setPosition(markerLatLng);
            map.setCenter(markerLatLng);
            $('#latitude').val(centreMarker.getPosition().lat());
            $('#longitude').val(centreMarker.getPosition().lng());
        } else {
            alert('Geocode was not successful for the following reason: ' + status);
        }

    });
}

function findLatLonAddress(latVal, lonVal) {
    var latlng = new google.maps.LatLng(latVal, lonVal);
    var geocoder = new google.maps.Geocoder();
    geocoder.geocode({'latLng': latlng}, function(results, status) {
    if (status == google.maps.GeocoderStatus.OK) {
      if (results[1]) {
        map.setZoom(11);
        map.setCenter(latlng);
        centreMarker.setPosition(latlng);
        //marker = new google.maps.Marker({
        //    position: latlng,
        //    map: map
        //});
        $("#address_geolocation").val(results[0].formatted_address);
      } else {
        alert('No results found');
      }
    } else {
      alert('Geocoder failed due to: ' + status);
    }
    });
}