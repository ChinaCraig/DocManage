/**
 * 智能文档语义检索应用
 */
class SemanticSearchApp {
    constructor() {
        this.selectedDocument = null;
        this.documentTree = [];
        this.originalDocumentTree = []; // 保存原始文档树数据
        this.chatHistory = [];
        this.isLoading = false;
        this.searchQuery = ''; // 搜索查询
        this.foldedFolders = new Set(); // 折叠的文件夹集合
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadDocumentTree();
        this.clearPathDisplay(); // 初始化时清除路径显示
    }

    bindEvents() {
        // 聊天输入事件
        const chatInput = document.getElementById('chat-input');
        const sendButton = document.getElementById('send-button');

        sendButton.addEventListener('click', () => this.sendMessage());
        
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // 搜索框事件
        const searchInput = document.getElementById('tree-search-input');
        const searchClear = document.getElementById('search-clear');

        searchInput.addEventListener('input', (e) => {
            this.handleSearch(e.target.value.trim());
        });

        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
            }
        });

        searchClear.addEventListener('click', () => {
            searchInput.value = '';
            this.handleSearch('');
            searchInput.focus();
        });

        // 监听搜索框的输入变化，显示/隐藏清除按钮
        searchInput.addEventListener('input', (e) => {
            const value = e.target.value.trim();
            searchClear.style.display = value ? 'block' : 'none';
            this.handleSearch(value);
        });
    }

    /**
     * 加载文档树
     */
    async loadDocumentTree() {
        try {
            const response = await fetch('/api/documents/tree');
            const result = await response.json();
            
            if (result.success) {
                this.documentTree = result.data;
                this.originalDocumentTree = [...this.documentTree]; // 复制原始文档树
                this.renderDocumentTree();
            } else {
                console.error('加载文档树失败:', result.error);
                this.showError('加载文档树失败');
            }
        } catch (error) {
            console.error('加载文档树异常:', error);
            this.showError('网络连接错误');
        }
    }

    /**
     * 渲染文档树
     */
    renderDocumentTree() {
        const treeContainer = document.getElementById('file-tree');
        treeContainer.innerHTML = this.renderTreeNodes(this.documentTree);
    }

    /**
     * 递归渲染树节点
     */
    renderTreeNodes(nodes, level = 0) {
        if (!nodes || nodes.length === 0) {
            return '';
        }

        return nodes.map(node => {
            const icon = this.getFileIcon(node);
            const indent = 'padding-left: ' + (level * 20 + (node.type === 'folder' ? 30 : 10)) + 'px;';
            const isFile = node.type === 'file';
            const hasChildren = node.children && node.children.length > 0;
            const isFolded = this.foldedFolders.has(node.id);
            
            // 搜索过滤
            const isVisible = this.isNodeVisible(node);
            const hiddenClass = isVisible ? '' : 'filtered-hidden';
            
            let html = `
                <div class="tree-item ${isFile ? 'file-item' : 'folder-item'} ${hasChildren ? 'has-children' : ''} ${hiddenClass}" 
                     data-id="${node.id}" 
                     data-type="${node.type}"
                     data-file-type="${node.file_type || ''}"
                     data-name="${node.name}"
                     style="${indent}">
            `;

            // 如果是文件夹且有子项，添加折叠按钮
            if (node.type === 'folder' && hasChildren) {
                html += `
                    <i class="bi bi-chevron-right folder-toggle ${isFolded ? '' : 'expanded'}" 
                       data-folder-id="${node.id}"></i>
                `;
            }

            html += `
                    <i class="bi ${icon}"></i>
                    <span>${this.highlightSearchText(node.name)}</span>
                </div>
            `;
            
            // 递归渲染子节点
            if (hasChildren) {
                const childrenClass = isFolded ? 'collapsed' : '';
                html += `<div class="tree-children ${childrenClass}" data-parent="${node.id}">${this.renderTreeNodes(node.children, level + 1)}</div>`;
            }
            
            return html;
        }).join('');
    }

    /**
     * 获取文件类型图标
     */
    getFileIcon(node) {
        if (node.type === 'folder') {
            return 'bi-folder icon-folder';
        }
        
        const fileType = node.file_type?.toLowerCase();
        switch (fileType) {
            case 'pdf':
                return 'bi-file-earmark-pdf icon-pdf';
            case 'docx':
            case 'doc':
                return 'bi-file-earmark-word icon-word';
            case 'xlsx':
            case 'xls':
                return 'bi-file-earmark-excel icon-excel';
            case 'jpg':
            case 'jpeg':
            case 'png':
            case 'gif':
            case 'bmp':
                return 'bi-file-earmark-image icon-image';
            case 'mp4':
            case 'avi':
            case 'mov':
            case 'wmv':
                return 'bi-file-earmark-play icon-video';
            default:
                return 'bi-file-earmark icon-file';
        }
    }

    /**
     * 发送消息
     */
    async sendMessage() {
        const chatInput = document.getElementById('chat-input');
        const message = chatInput.value.trim();
        
        if (!message || this.isLoading) {
            return;
        }

        // 清空输入框
        chatInput.value = '';
        
        // 添加用户消息
        this.addMessage('user', message);
        
        // 显示加载状态
        this.isLoading = true;
        const loadingId = this.addMessage('assistant', '<div class="loading"></div>', true);
        
        try {
            // 执行语义搜索
            const searchResponse = await fetch('/api/search/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: message,
                    top_k: 10,
                    document_id: this.selectedDocument?.id
                })
            });
            
            const searchResult = await searchResponse.json();
            
            if (searchResult.success && searchResult.data.results.length > 0) {
                await this.handleSearchResults(message, searchResult.data);
            } else {
                this.updateMessage(loadingId, '抱歉，没有找到相关的内容。请尝试使用其他关键词进行搜索。');
            }
            
        } catch (error) {
            console.error('搜索失败:', error);
            this.updateMessage(loadingId, '搜索过程中发生错误，请稍后重试。');
        } finally {
            this.isLoading = false;
        }
    }

    /**
     * 处理搜索结果
     */
    async handleSearchResults(query, searchData) {
        const results = searchData.results;
        
        // 构造回复消息
        let responseText = `根据您的查询"${query}"，我找到了${results.length}个相关结果：\n\n`;
        
        const documentGroups = {};
        results.forEach(result => {
            const docId = result.document.id;
            if (!documentGroups[docId]) {
                documentGroups[docId] = {
                    document: result.document,
                    chunks: []
                };
            }
            documentGroups[docId].chunks.push(result);
        });

        Object.values(documentGroups).forEach((group, index) => {
            responseText += `📄 **${group.document.name}**\n`;
            group.chunks.slice(0, 3).forEach((chunk, chunkIndex) => {
                const similarity = (chunk.score * 100).toFixed(1);
                responseText += `   ${chunkIndex + 1}. ${chunk.text.substring(0, 150)}${chunk.text.length > 150 ? '...' : ''} (相似度: ${similarity}%)\n`;
            });
            responseText += '\n';
        });

        // 更新消息
        const loadingElement = document.querySelector('.loading').closest('.message');
        this.updateMessage(loadingElement.dataset.messageId, responseText);
        
        // 高亮显示相关文档
        this.highlightRelevantDocuments(results);
        
        // 如果只有一个文档结果，自动预览
        if (Object.keys(documentGroups).length === 1) {
            const docId = parseInt(Object.keys(documentGroups)[0]);
            await this.previewDocument(docId, results[0].text);
        }
    }

    /**
     * 高亮显示相关文档
     */
    highlightRelevantDocuments(results) {
        // 清除之前的高亮
        document.querySelectorAll('.tree-item.highlight').forEach(item => {
            item.classList.remove('highlight');
        });

        // 添加新的高亮
        const relevantDocIds = [...new Set(results.map(r => r.document.id))];
        relevantDocIds.forEach(docId => {
            const treeItem = document.querySelector(`.tree-item[data-id="${docId}"]`);
            if (treeItem) {
                treeItem.classList.add('highlight');
                // 3秒后移除高亮
                setTimeout(() => {
                    treeItem.classList.remove('highlight');
                }, 3000);
            }
        });
    }

    /**
     * 预览文档
     */
    async previewDocument(documentId, highlightText = '') {
        try {
            // 清除之前的选中状态
            document.querySelectorAll('.tree-item.selected').forEach(item => {
                item.classList.remove('selected');
            });

            // 添加选中状态
            const treeItem = document.querySelector(`.tree-item[data-id="${documentId}"]`);
            if (treeItem) {
                treeItem.classList.add('selected');
                this.selectedDocument = {
                    id: documentId,
                    type: treeItem.dataset.type,
                    fileType: treeItem.dataset.fileType
                };
                
                // 更新路径显示
                this.updatePathDisplay(documentId);
            }

            // 获取文档详情
            const response = await fetch(`/api/documents/${documentId}/detail`);
            const result = await response.json();
            
            if (result.success) {
                await this.renderDocumentPreview(result.data, highlightText);
            } else {
                this.showError('加载文档详情失败');
            }
            
        } catch (error) {
            console.error('预览文档失败:', error);
            this.showError('预览文档时发生错误');
        }
    }

    /**
     * 渲染文档预览
     */
    async renderDocumentPreview(documentData, highlightText = '') {
        const previewTitle = document.getElementById('preview-title');
        const previewContent = document.getElementById('preview-content');
        
        // 更新标题
        previewTitle.innerHTML = `
            <i class="bi bi-eye"></i>
            ${documentData.name}
            <span class="badge bg-secondary ms-2">${documentData.file_type}</span>
        `;

        // 根据文件类型渲染不同的预览内容
        const fileType = documentData.file_type?.toLowerCase();
        
        try {
            let previewHtml = '';
            
            switch (fileType) {
                case 'pdf':
                    previewHtml = await this.renderPdfPreview(documentData, highlightText);
                    break;
                case 'word':
                case 'docx':
                case 'doc':
                    previewHtml = await this.renderWordPreview(documentData, highlightText);
                    break;
                case 'excel':
                case 'xlsx':
                case 'xls':
                    previewHtml = await this.renderExcelPreview(documentData, highlightText);
                    break;
                case 'image':
                case 'jpg':
                case 'jpeg':
                case 'png':
                case 'gif':
                case 'bmp':
                case 'tiff':
                case 'webp':
                    previewHtml = await this.renderImagePreview(documentData);
                    break;
                case 'video':
                case 'mp4':
                case 'avi':
                case 'mov':
                case 'wmv':
                case 'mkv':
                case 'flv':
                case 'webm':
                    previewHtml = await this.renderVideoPreview(documentData);
                    break;
                default:
                    previewHtml = this.renderDefaultPreview(documentData);
            }
            
            previewContent.innerHTML = previewHtml;
            
            // 如果是PDF文档，初始化模式切换功能
            if (fileType === 'pdf') {
                // 使用setTimeout确保DOM元素已经渲染
                setTimeout(() => {
                    this.initPdfModeSwitch(documentData, highlightText);
                }, 100);
            }
            
            // 如果是Word文档，初始化模式切换功能
            if (fileType === 'word' || fileType === 'docx' || fileType === 'doc') {
                setTimeout(() => {
                    this.initWordModeSwitch(documentData, highlightText);
                }, 100);
            }
            
            // 如果是Excel文档，初始化模式切换功能
            if (fileType === 'excel' || fileType === 'xlsx' || fileType === 'xls') {
                setTimeout(() => {
                    this.initExcelModeSwitch(documentData, highlightText);
                }, 100);
            }
            
        } catch (error) {
            console.error('渲染预览失败:', error);
            previewContent.innerHTML = `
                <div class="alert alert-warning">
                    <i class="bi bi-exclamation-triangle"></i>
                    无法预览此文件类型
                </div>
            `;
        }
    }

    /**
     * 渲染PDF预览
     */
    async renderPdfPreview(documentData, highlightText) {
        try {
            // 提供两种预览模式：原始PDF和文本提取
            return `
                <div class="pdf-preview">
                    <div class="preview-info mb-3">
                        <span class="badge bg-info">PDF文档</span>
                        <div class="btn-group btn-group-sm ms-3" role="group">
                            <button type="button" class="btn btn-outline-primary active" id="pdf-raw-mode">
                                <i class="bi bi-file-pdf"></i> 原始预览
                            </button>
                            <button type="button" class="btn btn-outline-secondary" id="pdf-text-mode">
                                <i class="bi bi-file-text"></i> 文本预览
                            </button>
                        </div>
                    </div>
                    
                    <!-- 原始PDF预览 -->
                    <div id="pdf-raw-container" class="pdf-container">
                        <iframe src="/api/preview/pdf/raw/${documentData.id}" 
                                class="pdf-iframe" 
                                frameborder="0"
                                title="PDF预览">
                            <p>您的浏览器不支持PDF预览。 
                               <a href="/api/preview/pdf/raw/${documentData.id}" target="_blank">点击此处在新窗口中打开</a>
                            </p>
                        </iframe>
                    </div>
                    
                    <!-- 文本提取预览 -->
                    <div id="pdf-text-container" class="pdf-text-container" style="display: none;">
                        <div class="loading-placeholder">
                            <div class="loading"></div>
                            <span>正在加载文本内容...</span>
                        </div>
                    </div>
                </div>
            `;
            
        } catch (error) {
            console.error('PDF预览失败:', error);
            return `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    PDF预览失败，请稍后重试
                </div>
            `;
        }
    }

    /**
     * 初始化PDF预览模式切换
     */
    initPdfModeSwitch(documentData, highlightText) {
        const rawModeBtn = document.getElementById('pdf-raw-mode');
        const textModeBtn = document.getElementById('pdf-text-mode');
        const rawContainer = document.getElementById('pdf-raw-container');
        const textContainer = document.getElementById('pdf-text-container');
        
        if (!rawModeBtn || !textModeBtn || !rawContainer || !textContainer) {
            return;
        }
        
        // 原始PDF模式
        rawModeBtn.addEventListener('click', () => {
            rawModeBtn.classList.add('btn-outline-primary', 'active');
            rawModeBtn.classList.remove('btn-outline-secondary');
            textModeBtn.classList.add('btn-outline-secondary');
            textModeBtn.classList.remove('btn-outline-primary', 'active');
            
            rawContainer.style.display = 'block';
            textContainer.style.display = 'none';
        });
        
        // 文本提取模式
        textModeBtn.addEventListener('click', async () => {
            textModeBtn.classList.add('btn-outline-primary', 'active');
            textModeBtn.classList.remove('btn-outline-secondary');
            rawModeBtn.classList.add('btn-outline-secondary');
            rawModeBtn.classList.remove('btn-outline-primary', 'active');
            
            rawContainer.style.display = 'none';
            textContainer.style.display = 'block';
            
            // 如果还没有加载文本内容，则加载
            if (textContainer.querySelector('.loading-placeholder')) {
                await this.loadPdfTextContent(documentData, highlightText, textContainer);
            }
        });
    }

    /**
     * 加载PDF文本内容
     */
    async loadPdfTextContent(documentData, highlightText, container) {
        try {
            const response = await fetch(`/api/preview/pdf/${documentData.id}`);
            const result = await response.json();
            
            if (result.success) {
                let content = result.data.content || '暂无内容';
                
                // 格式化内容，保持换行和段落结构
                content = this.formatPdfContent(content);
                
                // 如果有高亮文本，则高亮显示
                if (highlightText) {
                    content = this.highlightTextInContent(content, highlightText);
                }
                
                const textInfo = `
                    <div class="text-preview-info mb-3">
                        <span class="text-muted">页数: ${result.data.pages || '未知'}</span>
                        ${result.data.metadata && result.data.metadata.title ? 
                            `<span class="text-muted ms-2">标题: ${result.data.metadata.title}</span>` : ''}
                    </div>
                `;
                
                container.innerHTML = textInfo + `<div class="pdf-content">${content}</div>`;
            } else {
                container.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle"></i>
                        文本提取失败
                    </div>
                `;
            }
        } catch (error) {
            console.error('加载PDF文本内容失败:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    加载文本内容时发生错误
                </div>
            `;
        }
    }

    /**
     * 格式化PDF内容
     */
    formatPdfContent(content) {
        if (!content) return '暂无内容';
        
        // 将内容按页分割
        const pages = content.split(/--- 第 \d+ 页 ---/);
        
        let formattedContent = '';
        pages.forEach((pageContent, index) => {
            if (pageContent.trim()) {
                if (index > 0) {
                    formattedContent += `<div class="page-header">第 ${index} 页</div>`;
                }
                
                // 格式化段落
                const paragraphs = pageContent.split('\n\n');
                paragraphs.forEach(paragraph => {
                    const trimmed = paragraph.trim();
                    if (trimmed) {
                        // 处理换行，保持原始格式
                        const formatted = trimmed.replace(/\n/g, '<br>');
                        formattedContent += `<div class="pdf-paragraph">${formatted}</div>`;
                    }
                });
            }
        });
        
        return formattedContent || '暂无可显示内容';
    }

    /**
     * 渲染Word预览
     */
    async renderWordPreview(documentData, highlightText) {
        try {
            return `
                <div class="word-preview">
                    <div class="preview-info mb-3">
                        <span class="badge bg-primary">Word文档</span>
                        <div class="btn-group btn-group-sm ms-3" role="group">
                            <button type="button" class="btn btn-outline-primary active" id="word-text-mode">
                                <i class="bi bi-file-text"></i> 文本预览
                            </button>
                            <button type="button" class="btn btn-outline-info" id="word-download-mode">
                                <i class="bi bi-download"></i> 下载原文件
                            </button>
                        </div>
                    </div>
                    
                    <!-- 文本提取预览 -->
                    <div id="word-text-container" class="office-text-container">
                        <div class="loading-placeholder">
                            <div class="loading"></div>
                            <span>正在加载文档内容...</span>
                        </div>
                    </div>
                </div>
            `;
            
        } catch (error) {
            console.error('Word预览失败:', error);
            return `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    Word预览失败，请稍后重试
                </div>
            `;
        }
    }

    /**
     * 初始化Word预览模式切换
     */
    async initWordModeSwitch(documentData, highlightText) {
        const textModeBtn = document.getElementById('word-text-mode');
        const downloadBtn = document.getElementById('word-download-mode');
        const textContainer = document.getElementById('word-text-container');
        
        if (!textModeBtn || !downloadBtn || !textContainer) {
            return;
        }
        
        // 自动加载文本内容
        await this.loadWordTextContent(documentData, highlightText, textContainer);
        
        // 文本预览模式（默认激活）
        textModeBtn.addEventListener('click', () => {
            // 已经是默认模式，无需切换
        });
        
        // 下载模式
        downloadBtn.addEventListener('click', () => {
            window.open(`/api/preview/word/raw/${documentData.id}`, '_blank');
        });
    }

    /**
     * 加载Word文本内容
     */
    async loadWordTextContent(documentData, highlightText, container) {
        try {
            const response = await fetch(`/api/preview/word/${documentData.id}`);
            const result = await response.json();
            
            if (result.success) {
                let content = result.data.content || '暂无内容';
                const images = result.data.images || [];
                
                // 如果有高亮文本，则高亮显示
                if (highlightText) {
                    content = this.highlightTextInContent(content, highlightText);
                }
                
                const textInfo = `
                    <div class="text-preview-info mb-3">
                        <span class="text-muted">文档类型: Word</span>
                        ${result.data.metadata && result.data.metadata.title ? 
                            `<span class="text-muted ms-2">标题: ${result.data.metadata.title}</span>` : ''}
                        ${images.length > 0 ? 
                            `<span class="text-muted ms-2">图片: ${images.length}张</span>` : ''}
                    </div>
                `;
                
                // 构建内容HTML
                let contentHtml = `<div class="office-content">${content.replace(/\n/g, '<br>')}</div>`;
                
                // 如果有图片，显示图片区域
                if (images.length > 0) {
                    const imagesHtml = `
                        <div class="word-images-section mt-4">
                            <h6 class="text-muted mb-3">
                                <i class="bi bi-images"></i> 
                                文档中的图片 (${images.length}张)
                            </h6>
                            <div class="row">
                                ${images.map(image => `
                                    <div class="col-md-6 col-lg-4 mb-3">
                                        <div class="card">
                                            <img src="${image.url}" 
                                                 class="card-img-top word-image" 
                                                 alt="图片 ${image.index}"
                                                 data-image-url="${image.url}"
                                                 data-image-title="图片 ${image.index}"
                                                 style="height: 200px; object-fit: contain; cursor: pointer;">
                                            <div class="card-body p-2">
                                                <small class="text-muted">图片 ${image.index}</small>
                                                ${image.original_name ? 
                                                    `<br><small class="text-muted">${image.original_name}</small>` : ''}
                                            </div>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    `;
                    contentHtml += imagesHtml;
                }
                
                container.innerHTML = textInfo + contentHtml;
                
                // 绑定图片点击事件
                this.bindImageClickEvents(container);
                
            } else {
                container.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle"></i>
                        文本提取失败
                    </div>
                `;
            }
        } catch (error) {
            console.error('加载Word文本内容失败:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    加载文本内容时发生错误
                </div>
            `;
        }
    }

    /**
     * 绑定图片点击事件
     */
    bindImageClickEvents(container) {
        const images = container.querySelectorAll('.word-image');
        images.forEach(img => {
            img.addEventListener('click', (e) => {
                const imageUrl = e.target.dataset.imageUrl;
                const imageTitle = e.target.dataset.imageTitle;
                this.openImageModal(imageUrl, imageTitle);
            });
        });
    }

    /**
     * 打开图片模态框
     */
    openImageModal(imageUrl, imageTitle) {
        // 创建模态框HTML
        const modalHtml = `
            <div class="modal fade" id="imageModal" tabindex="-1" aria-labelledby="imageModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-lg modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="imageModalLabel">${imageTitle}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body text-center">
                            <img src="${imageUrl}" class="img-fluid" alt="${imageTitle}" style="max-height: 70vh;">
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                            <a href="${imageUrl}" target="_blank" class="btn btn-primary">在新窗口中打开</a>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // 移除之前的模态框
        const existingModal = document.getElementById('imageModal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // 添加新的模态框
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        // 显示模态框
        const modal = new bootstrap.Modal(document.getElementById('imageModal'));
        modal.show();
        
        // 模态框关闭后移除DOM元素
        document.getElementById('imageModal').addEventListener('hidden.bs.modal', function () {
            this.remove();
        });
    }

    /**
     * 渲染Excel预览
     */
    async renderExcelPreview(documentData, highlightText) {
        try {
            return `
                <div class="excel-preview">
                    <div class="preview-info mb-3">
                        <span class="badge bg-success">Excel表格</span>
                        <div class="btn-group btn-group-sm ms-3" role="group">
                            <button type="button" class="btn btn-outline-primary active" id="excel-data-mode">
                                <i class="bi bi-table"></i> 数据预览
                            </button>
                            <button type="button" class="btn btn-outline-info" id="excel-download-mode">
                                <i class="bi bi-download"></i> 下载原文件
                            </button>
                        </div>
                    </div>
                    
                    <!-- 数据提取预览 -->
                    <div id="excel-data-container" class="office-data-container">
                        <div class="loading-placeholder">
                            <div class="loading"></div>
                            <span>正在加载表格数据...</span>
                        </div>
                    </div>
                </div>
            `;
            
        } catch (error) {
            console.error('Excel预览失败:', error);
            return `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    Excel预览失败，请稍后重试
                </div>
            `;
        }
    }

    /**
     * 初始化Excel预览模式切换
     */
    async initExcelModeSwitch(documentData, highlightText) {
        const dataModeBtn = document.getElementById('excel-data-mode');
        const downloadBtn = document.getElementById('excel-download-mode');
        const dataContainer = document.getElementById('excel-data-container');
        
        if (!dataModeBtn || !downloadBtn || !dataContainer) {
            return;
        }
        
        // 自动加载数据内容
        await this.loadExcelDataContent(documentData, highlightText, dataContainer);
        
        // 数据预览模式（默认激活）
        dataModeBtn.addEventListener('click', () => {
            // 已经是默认模式，无需切换
        });
        
        // 下载模式
        downloadBtn.addEventListener('click', () => {
            window.open(`/api/preview/excel/raw/${documentData.id}`, '_blank');
        });
    }

    /**
     * 加载Excel数据内容
     */
    async loadExcelDataContent(documentData, highlightText, container) {
        try {
            const response = await fetch(`/api/preview/excel/${documentData.id}`);
            const result = await response.json();
            
            if (result.success) {
                const sheets = result.data.sheets || [];
                
                let content = '';
                if (sheets.length > 0) {
                    content = sheets.map((sheet, index) => {
                        const rows = sheet.data || [];
                        
                        let tableHtml = `
                            <div class="excel-sheet mb-4">
                                <h6 class="sheet-title">${sheet.name || `工作表 ${index + 1}`}</h6>
                                <div class="table-responsive">
                                    <table class="table table-sm table-bordered">
                        `;
                        
                        rows.forEach((row, rowIndex) => {
                            tableHtml += '<tr>';
                            row.forEach(cell => {
                                const cellContent = cell ? String(cell).replace(/\n/g, '<br>') : '';
                                tableHtml += `<td>${cellContent}</td>`;
                            });
                            tableHtml += '</tr>';
                            
                            // 限制显示行数，避免数据过多
                            if (rowIndex > 50) {
                                tableHtml += `<tr><td colspan="${row.length}" class="text-center text-muted">... 还有更多数据，请下载查看完整内容 ...</td></tr>`;
                                return false;
                            }
                        });
                        
                        tableHtml += '</table></div></div>';
                        return tableHtml;
                    }).join('');
                } else {
                    content = '<div class="alert alert-info">未找到表格数据</div>';
                }
                
                const dataInfo = `
                    <div class="text-preview-info mb-3">
                        <span class="text-muted">工作表数量: ${sheets.length}</span>
                        ${result.data.metadata && result.data.metadata.title ? 
                            `<span class="text-muted ms-2">标题: ${result.data.metadata.title}</span>` : ''}
                    </div>
                `;
                
                container.innerHTML = dataInfo + `<div class="excel-data-content">${content}</div>`;
            } else {
                container.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle"></i>
                        数据提取失败
                    </div>
                `;
            }
        } catch (error) {
            console.error('加载Excel数据内容失败:', error);
            container.innerHTML = `
                <div class="alert alert-danger">
                    <i class="bi bi-exclamation-triangle"></i>
                    加载数据内容时发生错误
                </div>
            `;
        }
    }

    /**
     * 渲染图片预览
     */
    async renderImagePreview(documentData) {
        return `
            <div class="image-preview text-center">
                <div class="preview-info mb-3">
                    <span class="badge bg-warning">图片文件</span>
                </div>
                <img src="/api/preview/image/${documentData.id}" 
                     class="img-fluid rounded shadow" 
                     style="max-height: 400px;"
                     alt="${documentData.name}"
                     onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEwMCIgZmlsbD0iI2VlZSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LXNpemU9IjE0IiBmaWxsPSIjYWFhIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBkeT0iLjNlbSI+5peg5rOV6aKE6KeI</dGV4dD48L3N2Zz4=';">
            </div>
        `;
    }

    /**
     * 渲染视频预览
     */
    async renderVideoPreview(documentData) {
        return `
            <div class="video-preview">
                <div class="preview-info mb-3">
                    <span class="badge bg-secondary">视频文件</span>
                </div>
                <video controls class="w-100 rounded shadow" style="max-height: 400px;">
                    <source src="/api/preview/video/${documentData.id}" type="video/mp4">
                    您的浏览器不支持视频播放。
                </video>
            </div>
        `;
    }

    /**
     * 渲染默认预览
     */
    renderDefaultPreview(documentData) {
        return `
            <div class="default-preview text-center">
                <div class="empty-state">
                    <i class="bi bi-file-earmark"></i>
                    <p>此文件类型暂不支持预览</p>
                    <p class="text-muted">${documentData.name}</p>
                </div>
            </div>
        `;
    }

    /**
     * 在内容中高亮显示文本
     */
    highlightTextInContent(content, highlightText) {
        if (!highlightText || !content) return content;
        
        const regex = new RegExp(`(${this.escapeRegExp(highlightText)})`, 'gi');
        return content.replace(regex, '<span class="highlight-text">$1</span>');
    }

    /**
     * 转义正则表达式特殊字符
     */
    escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    /**
     * 添加消息到聊天区域
     */
    addMessage(sender, content, isLoading = false) {
        const chatMessages = document.getElementById('chat-messages');
        const messageId = 'msg-' + Date.now();
        const time = new Date().toLocaleTimeString();
        
        const messageHtml = `
            <div class="message ${sender}" data-message-id="${messageId}">
                <div class="message-content">
                    <div class="message-text">${content}</div>
                    <div class="message-time">${time}</div>
                </div>
            </div>
        `;
        
        chatMessages.insertAdjacentHTML('beforeend', messageHtml);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return messageId;
    }

    /**
     * 更新消息内容
     */
    updateMessage(messageId, content) {
        const messageElement = typeof messageId === 'string' 
            ? document.querySelector(`[data-message-id="${messageId}"]`)
            : messageId;
            
        if (messageElement) {
            const textElement = messageElement.querySelector('.message-text');
            if (textElement) {
                textElement.innerHTML = content;
            }
        }
    }

    /**
     * 显示错误消息
     */
    showError(message) {
        this.addMessage('assistant', `❌ ${message}`);
    }

    /**
     * 处理搜索
     */
    handleSearch(query) {
        this.searchQuery = query.toLowerCase();
        this.renderDocumentTree();
        
        // 如果有搜索结果，展开所有匹配的路径
        if (query) {
            this.expandSearchResults();
        }
    }

    /**
     * 判断节点是否可见（搜索过滤）
     */
    isNodeVisible(node) {
        if (!this.searchQuery) {
            return true;
        }
        
        // 检查当前节点名称是否匹配
        if (node.name.toLowerCase().includes(this.searchQuery)) {
            return true;
        }
        
        // 检查子节点是否有匹配的
        if (node.children && node.children.length > 0) {
            return node.children.some(child => this.hasMatchingChild(child));
        }
        
        return false;
    }

    /**
     * 递归检查是否有匹配的子节点
     */
    hasMatchingChild(node) {
        if (node.name.toLowerCase().includes(this.searchQuery)) {
            return true;
        }
        
        if (node.children && node.children.length > 0) {
            return node.children.some(child => this.hasMatchingChild(child));
        }
        
        return false;
    }

    /**
     * 高亮搜索文本
     */
    highlightSearchText(text) {
        if (!this.searchQuery) {
            return text;
        }
        
        const regex = new RegExp(`(${this.escapeRegExp(this.searchQuery)})`, 'gi');
        return text.replace(regex, '<mark>$1</mark>');
    }

    /**
     * 展开搜索结果路径
     */
    expandSearchResults() {
        if (!this.searchQuery) {
            return;
        }
        
        // 找到所有匹配的节点，并展开其父路径
        this.expandMatchingPaths(this.originalDocumentTree);
    }

    /**
     * 递归展开匹配的路径
     */
    expandMatchingPaths(nodes, parentPath = []) {
        nodes.forEach(node => {
            const currentPath = [...parentPath, node.id];
            
            if (node.name.toLowerCase().includes(this.searchQuery)) {
                // 如果找到匹配项，展开其所有父路径
                parentPath.forEach(parentId => {
                    this.foldedFolders.delete(parentId);
                });
            }
            
            if (node.children && node.children.length > 0) {
                this.expandMatchingPaths(node.children, currentPath);
            }
        });
    }

    /**
     * 切换文件夹折叠状态
     */
    toggleFolder(folderId) {
        if (this.foldedFolders.has(folderId)) {
            this.foldedFolders.delete(folderId);
        } else {
            this.foldedFolders.add(folderId);
        }
        
        // 更新UI
        const folderToggle = document.querySelector(`[data-folder-id="${folderId}"]`);
        const treeChildren = document.querySelector(`[data-parent="${folderId}"]`);
        
        if (folderToggle && treeChildren) {
            const isCollapsed = this.foldedFolders.has(folderId);
            
            if (isCollapsed) {
                folderToggle.classList.remove('expanded');
                treeChildren.classList.add('collapsed');
            } else {
                folderToggle.classList.add('expanded');
                treeChildren.classList.remove('collapsed');
            }
        }
    }

    /**
     * 更新路径显示
     */
    updatePathDisplay(documentId) {
        const pathDisplay = document.getElementById('path-display');
        const pathBreadcrumb = document.getElementById('path-breadcrumb');
        
        // 查找文档路径
        const path = this.findDocumentPath(documentId, this.originalDocumentTree);
        
        if (path && path.length > 0) {
            // 显示路径区域
            pathDisplay.classList.remove('hidden');
            
            // 构建路径HTML
            const pathHtml = path.map((node, index) => {
                const icon = this.getFileIcon(node);
                const isLast = index === path.length - 1;
                const isClickable = node.type === 'file';
                
                let itemHtml = `
                    <div class="path-item ${isClickable ? 'clickable' : ''}" data-id="${node.id}" data-type="${node.type}">
                        <i class="bi ${icon} path-icon"></i>
                        <span>${node.name}</span>
                    </div>
                `;
                
                if (!isLast) {
                    itemHtml += `<i class="bi bi-chevron-right path-separator"></i>`;
                }
                
                return itemHtml;
            }).join('');
            
            pathBreadcrumb.innerHTML = pathHtml;
            
            // 绑定路径项点击事件
            pathBreadcrumb.querySelectorAll('.path-item.clickable').forEach(item => {
                item.addEventListener('click', async (e) => {
                    const nodeId = parseInt(e.currentTarget.dataset.id);
                    const nodeType = e.currentTarget.dataset.type;
                    
                    if (nodeType === 'file') {
                        await this.previewDocument(nodeId);
                    }
                });
            });
        } else {
            // 隐藏路径区域
            pathDisplay.classList.add('hidden');
        }
    }

    /**
     * 查找文档路径
     */
    findDocumentPath(documentId, nodes, currentPath = []) {
        for (const node of nodes) {
            const newPath = [...currentPath, node];
            
            if (node.id === documentId) {
                return newPath;
            }
            
            if (node.children && node.children.length > 0) {
                const foundPath = this.findDocumentPath(documentId, node.children, newPath);
                if (foundPath) {
                    return foundPath;
                }
            }
        }
        
        return null;
    }

    /**
     * 清除路径显示
     */
    clearPathDisplay() {
        const pathDisplay = document.getElementById('path-display');
        const pathBreadcrumb = document.getElementById('path-breadcrumb');
        
        pathDisplay.classList.add('hidden');
        pathBreadcrumb.innerHTML = '<span class="text-muted">未选择文档</span>';
    }

    /**
     * 在HTML内容中高亮显示文本
     */
    highlightTextInHtml(htmlContent, highlightText) {
        if (!highlightText || !htmlContent) return htmlContent;
        
        // 创建一个临时的DOM元素来处理HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = htmlContent;
        
        // 递归处理文本节点
        this.highlightTextInNode(tempDiv, highlightText);
        
        return tempDiv.innerHTML;
    }

    /**
     * 在DOM节点中高亮文本
     */
    highlightTextInNode(node, highlightText) {
        if (node.nodeType === Node.TEXT_NODE) {
            const text = node.textContent;
            const regex = new RegExp(`(${this.escapeRegExp(highlightText)})`, 'gi');
            if (regex.test(text)) {
                const highlightedText = text.replace(regex, '<span class="highlight-text">$1</span>');
                const wrapper = document.createElement('span');
                wrapper.innerHTML = highlightedText;
                node.parentNode.replaceChild(wrapper, node);
            }
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            // 递归处理子节点
            const children = Array.from(node.childNodes);
            children.forEach(child => this.highlightTextInNode(child, highlightText));
        }
    }
}

// 页面加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
    const app = new SemanticSearchApp();
    
    // 绑定文档树点击事件
    document.getElementById('file-tree').addEventListener('click', async (e) => {
        // 处理折叠按钮点击
        if (e.target.classList.contains('folder-toggle')) {
            e.stopPropagation();
            const folderId = parseInt(e.target.dataset.folderId);
            app.toggleFolder(folderId);
            return;
        }
        
        // 处理文档项点击
        const treeItem = e.target.closest('.tree-item');
        if (treeItem && treeItem.dataset.type === 'file') {
            const documentId = parseInt(treeItem.dataset.id);
            await app.previewDocument(documentId);
        }
    });
}); 