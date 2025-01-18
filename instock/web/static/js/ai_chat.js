$(document).ready(function() {
    // marked配置
    const renderer = new marked.Renderer();
    
    // 自定义标题渲染
    renderer.heading = function(text, level) {
        text = text.replace(/^[-#]+\s*/, '');  // 移除开头的 - 和 # 号
        return `<h${level} style="margin-top: 1.5em; color: #2c3e50; font-weight: 600;">${text}</h${level}>`;
    };

    // 优化段落渲染
    renderer.paragraph = function(text) {
        // 移除段落开头的特殊字符
        text = text.replace(/^[-#]+\s*/, '')  // 移除开头的 - 和 # 号
                   .replace(/^[=\-]{3,}\s*/, '')  // 移除开头的 === 或 --- 
                   .trim();
        return `<p>${text}</p>`;
    };

    // 优化列表项渲染
    renderer.listitem = function(text) {
        // 移除列表项中的特殊字符
        text = text.replace(/^[-#]+\s*/, '')  // 移除开头的 - 和 # 号
                   .replace(/^[=\-]{3,}\s*/, '')  // 移除开头的 === 或 ---
                   .trim();
        return `<li>${text}</li>`;
    };

    // 添加文本预处理
    const textPreprocess = function(text) {
        return text.replace(/^[-#=]{3,}\s*/gm, '')  // 移除每行开头的特殊字符序列
                  .replace(/^\s*[-#]+\s*/gm, '');   // 移除每行开头的 - 和 # 号
    };

    marked.use({
        renderer: renderer,
        gfm: true,
        breaks: true,
        sanitize: false,
        headerIds: false,
        mangle: false,
        walkTokens: function(token) {
            if (token.type === 'text' || token.type === 'paragraph') {
                token.text = textPreprocess(token.text);
            }
        }
    });

    let messageBuffer = '';
    let lastChar = '';
    let tempBuffer = ''; // 用于临时存储可能的标题内容

    function appendMessage(message, isUser) {
        const messageHtml = `
            <div class="message-group">
                <div class="message ${isUser ? 'user' : 'ai'}">
                    <div class="message-avatar">${isUser ? '我' : 'AI'}</div>
                    <div class="message-content">${message}</div>
                </div>
            </div>
        `;
        
        const $messages = $('#chatMessages');
        $messages.append(messageHtml);
        $messages.scrollTop($messages[0].scrollHeight);
        return $messages.children().last().find('.message-content');
    }

    // 添加设备检测函数
    function isMobileDevice() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) 
            || window.innerWidth <= 768;
    }

    async function sendMessage() {
        const message = $('#messageInput').val().trim();
        if (!message) return;

        $('#messageInput').prop('disabled', true);
        $('#sendButton').prop('disabled', true);
        
        const userDiv = appendMessage(message, true);
        $('#messageInput').val('');
        
        const aiContentDiv = appendMessage('', false);
        messageBuffer = '';
        lastChar = '';

        try {
            const response = await fetch('/instock/ai_chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                body: 'message=' + encodeURIComponent(message)
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const {done, value} = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    
                    const data = line.slice(6).trim();
                    if (!data || data === '[DONE]') continue;
                    
                    if (data.startsWith('error:')) {
                        aiContentDiv.text('错误: ' + data.substring(6));
                        break;
                    }

                    // 优化文本处理
                    if (data === '') {
                        if (lastChar !== '\n') {
                            messageBuffer += '\n';
                        }
                    } else if (data === '#') {
                        if (lastChar !== '\n') {
                            messageBuffer += '\n\n';
                        }
                        messageBuffer += '#';
                    } else if (data.startsWith('# ')) {
                        if (lastChar !== '\n') {
                            messageBuffer += '\n\n';
                        }
                        messageBuffer += data;
                    } else if (data === '-') {
                        if (lastChar !== '\n') {
                            messageBuffer += '\n';
                        }
                        messageBuffer += '- ';
                    } else {
                        messageBuffer += data;
                        // 在句号等标点后添加换行
                        if (data.match(/[。！？：]/)) {
                            messageBuffer += '\n';
                        }
                    }

                    lastChar = data[data.length - 1] || lastChar;
                    
                    // 处理文本并渲染
                    const processedText = messageBuffer
                        .replace(/(?<=\n)#+(?=\s)/g, '') // 移除行首的#号
                        .replace(/\n{3,}/g, '\n\n')      // 规范化多余空行
                        .trim();
                    
                    aiContentDiv.html(marked.parse(processedText));
                }
            }

            // 最终渲染时额外处理
            const finalText = messageBuffer
                .replace(/(?<=\n)#+(?=\s)/g, '')
                .replace(/\n{3,}/g, '\n\n')
                .trim();
            aiContentDiv.html(marked.parse(finalText));
            
        } catch (error) {
            console.error('请求错误:', error);
            aiContentDiv.text('连接错误，请重试');
        } finally {
            $('#messageInput').prop('disabled', false);
            $('#sendButton').prop('disabled', false);
            
            // 仅在PC端时自动聚焦
            if (!isMobileDevice()) {
                $('#messageInput').focus();
            }
        }
    }

    function toggleMessage(element) {
        const preview = element.querySelector('.text-preview');
        const full = element.querySelector('.text-full');
        const btn = element.querySelector('.expand-btn');
        
        if (preview && full && btn) {
            if (getComputedStyle(preview).display !== 'none') {
                preview.style.display = 'none';
                full.style.display = 'block'; // 改为 block
                btn.textContent = '收起';
            } else {
                preview.style.display = 'block'; // 改为 block
                full.style.display = 'none';
                btn.textContent = '展开';
            }
        }
    }

    // 事件绑定
    $('#sendButton').on('click', sendMessage);
    
    // 添加一个变量来跟踪键盘状态
    let isKeyboardVisible = false;
    let windowHeight = window.innerHeight;
    
    // 监听窗口大小变化来检测键盘状态
    window.addEventListener('resize', () => {
        // 如果新的窗口高度小于原始高度，说明键盘弹出
        isKeyboardVisible = window.innerHeight < windowHeight;
        windowHeight = window.innerHeight;
    });
    
    // 修改输入框事件处理
    $('#messageInput').on('focus touchstart', function(e) {
        // 只在移动端且键盘未弹出时执行滚动
        if (isMobileDevice() && !isKeyboardVisible) {
            setTimeout(() => {
                const $messages = $('#chatMessages');
                $messages.scrollTop($messages[0].scrollHeight);
            }, 300);
        }
    });
    
    $('#messageInput').on('keypress', function(e) {
        if (e.which === 13 && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // 初始化时处理已有的markdown内容
    $('.message.ai .message-content').each(function() {
        const $content = $(this);
        const rawContent = $content.text();
        $content.html(marked.parse(rawContent));
    });

    // 页面加载完成后，仅在PC端自动聚焦输入框
    if (!isMobileDevice()) {
        $('#messageInput').focus();
    }
});
