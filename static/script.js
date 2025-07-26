$(document).ready(function () {
    function loadTweets() {
        $.ajax({
            url: '/api/tweets',
            method: 'GET',
            success: function (data) {
                $('#feed').empty();
                data.forEach(tweet => {
                    const $tweet = $('<div>').addClass('tweet');
                    const $header = $('<div>').addClass('tweet-header');
                    if (tweet.avatar) {
                        $header.append(
                            $('<img>')
                              .attr('src', '/static/uploads/' + tweet.avatar)
                              .addClass('avatar-small')
                        );
                    }
                    $header.append(
                        $('<a>')
                          .attr('href', '/profile/' + encodeURIComponent(tweet.username))
                          .addClass('username')
                          .text(tweet.username)
                    );
                    $tweet.append($header);

                    $tweet.append(
                        $('<div>')
                          .addClass('tweet-content')
                          .text(tweet.content)
                    );

                    $tweet.append(
                        $('<div>')
                          .addClass('timestamp')
                          .text(new Date(tweet.timestamp).toLocaleString())
                    );

                    $('#feed').append($tweet);
                });
            }
        });
    }

    $('#tweet-button').click(function () {
        const content = $('#tweet-content').val();
        if (!content.trim()) {
            alert('テキストを入力してください。');
            return;
        }
        $.ajax({
            url: '/api/tweets',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({ content }),
            success: function (tweet) {
                $('#tweet-content').val('');
                loadTweets();
            },
            error: function () {
                alert('投稿に失敗しました。');
            }
        });
    });

    loadTweets();
});
