$(document).ready(function () {
    // Track tweets liked by current user in this session
    let likedTweetIds = [];

    function buildThread(tweets) {
        const map = {}, roots = [];
        tweets.forEach(t => map[t.id] = {...t, replies: []});
        tweets.forEach(t => {
            if (t.parent_id) {
                map[t.parent_id] && map[t.parent_id].replies.push(map[t.id]);
            } else {
                roots.push(map[t.id]);
            }
        });
        return roots;
    }

    function loadTweets() {
        $.ajax({
            url: '/api/tweets',
            method: 'GET',
            success: function (data) {
                const threads = buildThread(data);
                function renderTweets(list, container, indent=0) {
                    list.forEach(tweet => {
                        const $tweet = $('<div>').addClass('tweet').css('margin-left', indent * 20 + 'px');
                        const $header = $('<div>').addClass('tweet-header');
                        if (tweet.avatar) {
                            $header.append($('<img>').attr('src', '/static/uploads/' + tweet.avatar).addClass('avatar-small'));
                        }
                        $header.append($('<a>').attr('href', '/profile/' + encodeURIComponent(tweet.username)).addClass('username').text(tweet.username));
                        $tweet.append($header);
                        $tweet.append($('<div>').addClass('tweet-content').text(tweet.content));
                        const $footer = $('<div>').addClass('tweet-footer');
                        $footer.append($('<span>').addClass('timestamp').text(new Date(tweet.timestamp).toLocaleString()));
                        $footer.append($('<button>').addClass('reply-button').attr('data-id', tweet.id).text('返信'));
                        const heart = likedTweetIds.includes(tweet.id) ? '♡' : '♡';
                        const $likeBtn = $('<button>')
                          .addClass('like-button')
                          .attr('data-id', tweet.id)
                          .text(heart + ' ' + tweet.like_count);
                        $footer.append($likeBtn);
                        if (tweet.username === window.CURRENT_USER) {
                            $footer.append(
                                $('<button>')
                                  .addClass('delete-button')
                                  .attr('data-id', tweet.id)
                                  .text('削除')
                            );
                        }
                        container.append($tweet.append($footer));
                        // Render replies recursively
                        if (tweet.replies.length) renderTweets(tweet.replies, container, indent+1);
                    });
                }
                $('#feed').empty();
                renderTweets(threads, $('#feed'));
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
                alert('投稿に失敗しました。ログインしているか確認してください。');
            }
        });
    });

    $('#feed').on('click', '.reply-button', function() {
        const id = $(this).data('id');
        const $form = $(`
            <div class="reply-form">
              <input type="text" class="reply-content" placeholder="返信を入力"/>
              <button class="submit-reply" data-id="${id}">送信</button>
            </div>
        `);
        $(this).closest('.tweet').append($form);
    });
    $('#feed').on('click', '.submit-reply', function() {
        const parent_id = $(this).data('id');
        const content = $(this).siblings('.reply-content').val();
        $.ajax({
            url: '/api/tweets',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({content, parent_id}),
            success: () => loadTweets(),
            error: () => loadTweets()
        });
    });

    $('#feed').on('click', '.like-button', function(e) {
        const tweet_id = $(this).data('id');
        const $btn = $(this);
        $.post(`/api/tweets/${tweet_id}/likes`, function(res) {
            if (likedTweetIds.includes(tweet_id)) {
                likedTweetIds = likedTweetIds.filter(id => id !== tweet_id);
            } else {
                likedTweetIds.push(tweet_id);
            }
            loadTweets();
        }, 'json');
    });

    $('#feed').on('click', '.delete-button', function() {
        const tweet_id = $(this).data('id');
        if (!confirm('本当にこの投稿を削除しますか？')) return;
        $.ajax({
            url: `/api/tweets/${tweet_id}`,
            method: 'DELETE',
            success: function() {
                loadTweets();
            },
            error: function() {
                alert('削除に失敗しました。');
                loadTweets();
            }
        });
    });

    loadTweets();
    // Poll for new tweets every 10 seconds
    setInterval(loadTweets, 10000);
});
