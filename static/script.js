$(document).ready(function () {
    function loadTweets() {
        $.ajax({
            url: '/api/tweets',
            method: 'GET',
            success: function (data) {
                $('#feed').empty();
                data.forEach(tweet => {
                    const tweetHtml = $(`
            <div class="tweet">
                <div class="tweet-header">
                    ${tweet.avatar ? `<img src="/static/uploads/${tweet.avatar}" class="avatar-small">` : ''}
                    <a href="/profile/${tweet.username}" class="username">${tweet.username}</a>
                </div>
                <div class="tweet-content">${tweet.content}</div>
                <div class="timestamp">${new Date(tweet.timestamp).toLocaleString()}</div>
            </div>
        `);
                    $('#feed').append(tweetHtml);
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
