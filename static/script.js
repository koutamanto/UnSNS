function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  if (outputArray.length === 64) {
    const uncompressed = new Uint8Array(65);
    uncompressed[0] = 0x04;
    uncompressed.set(outputArray, 1);
    return uncompressed;
  }
  return outputArray;
}
  
async function askNotificationPermission() {
  const result = await window.Notification.requestPermission();
  if (result !== 'granted') {
    alert('通知を許可しないとプッシュ通知は届きません');
    return false;
  }
  return true;
}

async function subscribePush() {
  // try {
  const registrations = await navigator.serviceWorker.getRegistrations();
  const subscription = await registrations[0].pushManager.subscribe({
  userVisibleOnly: true,
  applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
  });
  // alert(subscription);
  // サーバーへ購読情報を送信
  fetch('/subscribe', {
  method: 'POST',
  headers: {
      'Content-Type': 'application/json'
  },
  body: JSON.stringify(subscription)
  });
  console.log('Subscribed to push notifications');
  // } catch (error) {
  //   console.error('Failed to subscribe to push notifications', error);
  // }
}

// コメント折り畳み機能
function setupCommentToggle() {
  $(document).on('click', '.comment-toggle', function(e) {
    e.preventDefault();
    const $toggleBtn = $(this);
    const $commentsContainer = $toggleBtn.next('.comments-container');
    const $icon = $toggleBtn.find('.comment-toggle-icon');
    const $text = $toggleBtn.find('.comment-toggle-text');
    
    if ($commentsContainer.hasClass('expanded')) {
      $commentsContainer.removeClass('expanded').addClass('collapsed');
      $toggleBtn.removeClass('expanded');
      $text.text('コメントを表示');
    } else {
      $commentsContainer.removeClass('collapsed').addClass('expanded');
      $toggleBtn.addClass('expanded');
      $text.text('コメントを非表示');
    }
  });
}

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
                        if (tweet.image) {
                            $tweet.append(
                                $('<img>')
                                  .attr('src', '/static/uploads/' + tweet.image)
                                  .addClass('tweet-image')
                            );
                        }
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
                        $tweet.append($footer);
                        
                        // 返信がある場合はコメント折り畳み機能を追加
                        if (tweet.replies.length > 0) {
                            const $commentToggle = $(`
                                <button class="comment-toggle">
                                    <span class="comment-toggle-icon">▶</span>
                                    <span class="comment-toggle-text">コメントを表示</span>
                                    <span class="comment-count">(${tweet.replies.length}件)</span>
                                </button>
                            `);
                            const $commentsContainer = $('<div>').addClass('comments-container collapsed');
                            
                            $tweet.append($commentToggle);
                            $tweet.append($commentsContainer);
                            
                            // 返信を再帰的にレンダリング（コメントコンテナ内に）
                            renderTweets(tweet.replies, $commentsContainer, 0);
                        }
                        
                        container.append($tweet);
                    });
                }
                $('#feed').empty();
                renderTweets(threads, $('#feed'));
            }
        });
    }

    $('#tweet-button').click(function () {
        const content = $('#tweet-content').val().trim();
        if (!content) {
            alert('テキストを入力してください。');
            return;
        }
        const formData = new FormData();
        formData.append('content', content);
        const fileInput = $('#tweet-image')[0];
        if (fileInput && fileInput.files.length) {
            const file = fileInput.files[0];
            if (!file.type.startsWith('image/')) {
                alert('画像ファイルを選択してください。');
                return;
            }
            formData.append('image', file);
        }
        $.ajax({
            url: '/api/tweets',
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function (tweet) {
                $('#tweet-content').val('');
                $('#tweet-image').val('');
                loadTweets();
            },
            error: function () {
                alert('投稿に失敗しました。ログインが必要です。');
            }
        });
    });

    $('#feed').on('click', '.reply-button', function() {
        const id = $(this).data('id');
        const $tweet = $(this).closest('.tweet');
        const existing = $tweet.find('.reply-form');
        if (existing.length) {
            existing.remove();
        } else {
            const $form = $(`
                <div class="reply-form">
                  <input type="text" class="reply-content" placeholder="返信を入力"/>
                  <button class="submit-reply" data-id="${id}">送信</button>
                </div>
            `);
            $tweet.append($form);
        }
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
    
    $('#enable-push').click(async () => {
        if (await askNotificationPermission()) {
          try {
            await subscribePush();   // ← ここで待機する
            alert('プッシュ通知がオンになりました');
          } catch (err) {
            console.error('購読に失敗:', err);
            alert('プッシュ通知の有効化に失敗しました');
          }
        }
    });

    // 通知がすでに許可されている場合はボタンを非表示
    if (window.Notification && window.Notification.permission === 'granted') {
      $('#enable-push').hide();
    }
    
    // Service Worker 登録 (もしまだなら)
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/static/service-worker.js')
        .catch(err => alert('SW登録失敗:', err));
    }
    if (window.Notification && window.Notification.permission === 'granted') {
        subscribePush();
    }
    
    // コメント折り畳み機能を初期化
    setupCommentToggle();
    
    loadTweets();
    // Poll for new tweets every 10 seconds
    setInterval(loadTweets, 10000);
});

