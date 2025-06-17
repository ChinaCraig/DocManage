/**
 * 标准化消息内容渲染组件
 * 支持多种内容类型的统一渲染
 */

class MessageRenderer {
    
    /**
     * 渲染标准化消息
     * @param {Object} message - 标准化消息对象
     * @returns {HTMLElement} 渲染后的DOM元素
     */
    static renderMessage(message) {
        const messageContainer = document.createElement('div');
        messageContainer.className = 'message-container';
        messageContainer.setAttribute('data-message-id', message.message_id);
        messageContainer.setAttribute('data-role', message.role);
        messageContainer.setAttribute('data-timestamp', message.timestamp);
        
        // 添加消息头部（可选）
        if (message.role === 'assistant') {
            const header = this.createMessageHeader(message);
            messageContainer.appendChild(header);
        }
        
        // 渲染内容
        const contentContainer = document.createElement('div');
        contentContainer.className = 'message-content';
        
        if (message.content && Array.isArray(message.content)) {
            message.content.forEach(contentItem => {
                const element = this.renderContentItem(contentItem);
                if (element) {
                    contentContainer.appendChild(element);
                }
            });
        }
        
        messageContainer.appendChild(contentContainer);
        return messageContainer;
    }
    
    /**
     * 创建消息头部
     * @param {Object} message - 消息对象
     * @returns {HTMLElement} 头部元素
     */
    static createMessageHeader(message) {
        const header = document.createElement('div');
        header.className = 'message-header';
        
        const timestamp = new Date(message.timestamp).toLocaleString('zh-CN');
        header.innerHTML = `
            <span class="message-role">🤖 AI助手</span>
            <span class="message-time">${timestamp}</span>
        `;
        
        return header;
    }
    
    /**
     * 渲染单个内容项
     * @param {Object} contentItem - 内容项对象
     * @returns {HTMLElement|null} 渲染后的元素
     */
    static renderContentItem(contentItem) {
        if (!contentItem || !contentItem.type) {
            return null;
        }
        
        switch (contentItem.type) {
            case 'text':
                return this.renderText(contentItem.data);
            case 'markdown':
                return this.renderMarkdown(contentItem.data);
            case 'table':
                return this.renderTable(contentItem.data);
            case 'image':
                return this.renderImage(contentItem.data);
            case 'code':
                return this.renderCode(contentItem.data);
            case 'tool_call':
                return this.renderToolCall(contentItem.data);
            case 'file_link':
                return this.renderFileLink(contentItem.data);
            case 'link':
                return this.renderLink(contentItem.data);
            default:
                console.warn('未知的内容类型:', contentItem.type);
                return this.renderText(`[未知内容类型: ${contentItem.type}]`);
        }
    }
    
    /**
     * 渲染纯文本
     * @param {string} text - 文本内容
     * @returns {HTMLElement} 文本元素
     */
    static renderText(text) {
        const element = document.createElement('div');
        element.className = 'content-text';
        element.textContent = text;
        return element;
    }
    
    /**
     * 渲染Markdown内容
     * @param {string} markdown - Markdown文本
     * @returns {HTMLElement} Markdown元素
     */
    static renderMarkdown(markdown) {
        const element = document.createElement('div');
        element.className = 'content-markdown';
        
        // 简单的Markdown渲染（可以后续集成专门的Markdown库）
        let html = markdown
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/^\- (.*$)/gim, '<li>$1</li>')
            .replace(/\n/g, '<br>');
        
        // 处理列表
        html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
        
        element.innerHTML = html;
        return element;
    }
    
    /**
     * 渲染表格
     * @param {Object} tableData - 表格数据 {headers: [], rows: [[]]}
     * @returns {HTMLElement} 表格元素
     */
    static renderTable(tableData) {
        if (!tableData.headers || !tableData.rows) {
            return this.renderText('[表格数据格式错误]');
        }
        
        const container = document.createElement('div');
        container.className = 'content-table-container';
        
        const table = document.createElement('table');
        table.className = 'content-table';
        
        // 创建表头
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');
        tableData.headers.forEach(header => {
            const th = document.createElement('th');
            th.textContent = header;
            headerRow.appendChild(th);
        });
        thead.appendChild(headerRow);
        table.appendChild(thead);
        
        // 创建表体
        const tbody = document.createElement('tbody');
        tableData.rows.forEach(rowData => {
            const row = document.createElement('tr');
            rowData.forEach(cellData => {
                const td = document.createElement('td');
                td.textContent = cellData;
                row.appendChild(td);
            });
            tbody.appendChild(row);
        });
        table.appendChild(tbody);
        
        container.appendChild(table);
        return container;
    }
    
    /**
     * 渲染图片
     * @param {Object} imageData - 图片数据 {url: string, alt?: string}
     * @returns {HTMLElement} 图片元素
     */
    static renderImage(imageData) {
        const container = document.createElement('div');
        container.className = 'content-image-container';
        
        const img = document.createElement('img');
        img.src = imageData.url;
        img.alt = imageData.alt || '图片';
        img.className = 'content-image';
        img.loading = 'lazy';
        
        // 添加错误处理
        img.onerror = function() {
            this.style.display = 'none';
            const errorText = document.createElement('div');
            errorText.className = 'image-error';
            errorText.textContent = `图片加载失败: ${imageData.alt || imageData.url}`;
            container.appendChild(errorText);
        };
        
        container.appendChild(img);
        return container;
    }
    
    /**
     * 渲染代码块
     * @param {Object} codeData - 代码数据 {language: string, content: string}
     * @returns {HTMLElement} 代码元素
     */
    static renderCode(codeData) {
        const container = document.createElement('div');
        container.className = 'content-code-container';
        
        // 添加语言标签
        if (codeData.language) {
            const langLabel = document.createElement('div');
            langLabel.className = 'code-language';
            langLabel.textContent = codeData.language;
            container.appendChild(langLabel);
        }
        
        const pre = document.createElement('pre');
        const code = document.createElement('code');
        code.className = `language-${codeData.language || 'text'}`;
        code.textContent = codeData.content;
        
        pre.appendChild(code);
        container.appendChild(pre);
        
        // 添加复制按钮
        const copyBtn = document.createElement('button');
        copyBtn.className = 'code-copy-btn';
        copyBtn.textContent = '复制';
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(codeData.content).then(() => {
                copyBtn.textContent = '已复制';
                setTimeout(() => copyBtn.textContent = '复制', 2000);
            });
        };
        container.appendChild(copyBtn);
        
        return container;
    }
    
    /**
     * 渲染工具调用
     * @param {Object} toolData - 工具数据 {tool: string, params: object, result?: any, user_visible: boolean}
     * @returns {HTMLElement} 工具调用元素
     */
    static renderToolCall(toolData) {
        if (!toolData.user_visible) {
            return null; // 不显示用户不可见的工具调用
        }
        
        const container = document.createElement('div');
        container.className = 'content-tool-call';
        
        const header = document.createElement('div');
        header.className = 'tool-header';
        header.innerHTML = `
            <span class="tool-icon">🛠️</span>
            <span class="tool-name">${toolData.tool}</span>
        `;
        container.appendChild(header);
        
        // 显示参数
        if (toolData.params && Object.keys(toolData.params).length > 0) {
            const paramsDiv = document.createElement('div');
            paramsDiv.className = 'tool-params';
            paramsDiv.innerHTML = `<strong>参数:</strong> ${JSON.stringify(toolData.params, null, 2)}`;
            container.appendChild(paramsDiv);
        }
        
        // 显示结果
        if (toolData.result) {
            const resultDiv = document.createElement('div');
            resultDiv.className = 'tool-result';
            resultDiv.innerHTML = `<strong>结果:</strong> ${typeof toolData.result === 'object' ? JSON.stringify(toolData.result, null, 2) : toolData.result}`;
            container.appendChild(resultDiv);
        }
        
        return container;
    }
    
    /**
     * 渲染文件链接
     * @param {Object} fileData - 文件数据 {url: string, filename: string, description?: string}
     * @returns {HTMLElement} 文件链接元素
     */
    static renderFileLink(fileData) {
        const container = document.createElement('div');
        container.className = 'content-file-link';
        
        const link = document.createElement('a');
        link.href = fileData.url;
        link.target = '_blank';
        link.className = 'file-link';
        
        const icon = document.createElement('span');
        icon.className = 'file-icon';
        icon.textContent = '📄';
        
        const filename = document.createElement('span');
        filename.className = 'file-name';
        filename.textContent = fileData.filename;
        
        link.appendChild(icon);
        link.appendChild(filename);
        
        if (fileData.description) {
            const desc = document.createElement('span');
            desc.className = 'file-description';
            desc.textContent = fileData.description;
            link.appendChild(desc);
        }
        
        container.appendChild(link);
        return container;
    }
    
    /**
     * 渲染普通链接
     * @param {Object} linkData - 链接数据 {url: string, title: string}
     * @returns {HTMLElement} 链接元素
     */
    static renderLink(linkData) {
        const container = document.createElement('div');
        container.className = 'content-link';
        
        const link = document.createElement('a');
        link.href = linkData.url;
        link.target = '_blank';
        link.textContent = linkData.title;
        link.className = 'external-link';
        
        container.appendChild(link);
        return container;
    }
}

// 导出到全局作用域
window.MessageRenderer = MessageRenderer; 