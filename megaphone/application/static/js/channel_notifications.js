// Taken from: http://stackoverflow.com/questions/6589559/appengine-channel-no-messages-arrive
// Channel API support
$().ready(function(){
    // answer.html hides all td by default.
    $(".answer_td").slideDown(200);

    var channel = new goog.appengine.Channel(CHANNEL_TOKEN);
    if (channel) {
        var socket = channel.open();
        socket.onopen = onOpened;
        socket.onmessage = onMessage;
        socket.onerror = onError;
        socket.onclose = onClose;
    } else {
        console.log("No Channel token specified. Skipping.");
    }
});

function tell_user(message) {
    $('#channel-messages').append(message + '<br />');
}

function onOpened() {
    console.log('onOpened');
}

function onMessage(msg_obj) {
    var json_str = msg_obj["data"];
    var info = JSON.parse(json_str);
    var type = info["type"];

    switch(type) {
    case 'new_question':
        console.log('onMessage: new_question');
        var url = info["url"];
        var title = info["title"];
        var msg = info["msg"];
        tell_user(msg);
        break;
    case 'new_answer':
        console.log('onMessage: new_answer');
        if ($('tbody#answers').length == 0) {
            // if we don't have a table to append it to, just alert the user to the new answer
            var msg = info["msg"];
            tell_user(msg);
        } else {
            // Prepend the new answer and slideDown. This works in conjunction with answer.html
            var url = info["url"];
            $.get(url, function(data, status){

                // if there were no answers before, delete the placeholder
                $("#answers tr#empty").fadeOut();
                $("#answers tr#empty").remove();

                $('tbody#answers').prepend(data);
                $(".answer_td").slideDown(1000);

                tell_user('A new answer has been submitted. See below.');
            });
        }
        break;
    default:
        console.log('onMessage: unsupported type: ' + type);
    }
}

function onError(obj) {
    console.log('onError');
}

function onClose(obj) {
    console.log('onClose');
}
