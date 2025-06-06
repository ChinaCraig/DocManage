// 全局变量
let currentMode = 'unified'; // 统一模式，不再区分search和manage
let selectedNode = null;
let currentParentId = null;
let selectedFiles = [];
let currentPreviewDocument = null;
let searchQuery = '';
let chatHistory = [];
let nodeMap = {}; // 节点映射，用于快速查找
let vectorizationMode = false; // 向量化模式标志
let uploadAreaInitialized = false; // 上传区域初始化标志

// LLM相关全局变量
let availableLLMModels = [];
let selectedLLMModel = '';
let llmFeatures = {
    query_optimization: false,
    result_reranking: false,
    answer_generation: false
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 初始化统一界面
    initUnifiedInterface();
});

// ============ 统一界面初始化 ============

function initUnifiedInterface() {
    // 初始化聊天输入
    initChatInput();
    
    // 初始化搜索功能
    initSearchInput();
    
    // 初始化LLM模型选择器
    initLLMModelSelector();
    
    // 初始化上传功能（只初始化一次）
    if (!uploadAreaInitialized) {
        initUploadArea();
        uploadAreaInitialized = true;
    }
    
    // 加载文档树
    loadFileTree();
    
    // 加载统计信息
    loadStats();

    // 隐藏右键菜单
    document.addEventListener('click', hideContextMenu);
    
    // 添加键盘快捷键支持
    document.addEventListener('keydown', function(e) {
        // 按Escape键取消选择
        if (e.key === 'Escape') {
            clearSelection();
            hideContextMenu();
        }
    });
    
    // 初始显示空状态
    showEmptyState();
}

function showEmptyState() {
    const previewContent = document.getElementById('previewContent');
    const previewActions = document.getElementById('previewActions');
    
    // 显示预览区域的空状态
    previewContent.innerHTML = `
        <div class="preview-main-content">
            <div class="empty-state">
                <i class="bi bi-file-earmark-text"></i>
                <h4>文档预览</h4>
                <p>请选择一个文档进行预览</p>
                <small class="text-muted">支持PDF、Word、Excel、图片等多种格式</small>
            </div>
        </div>
    `;
    
    // 隐藏操作按钮
    previewActions.style.display = 'none';
    
    // 隐藏向量化面板
    closeVectorization();
}

// ============ 文档选择和预览 ============

async function showDocumentDetail(node) {
    try {
        if (!node || !node.id) {
            console.error('showDocumentDetail: Invalid node provided', node);
            showError('无效的文档节点');
            return;
        }

        const response = await fetch(`/api/documents/${node.id}/detail`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            const doc = result.data;
            
            if (!doc) {
                throw new Error('文档数据为空');
            }
            
            currentPreviewDocument = doc;
            
            // 更新预览标题
            updatePreviewTitle(doc);
            
            // 显示操作按钮
            showPreviewActions(doc);
            
            // 如果是文件，加载预览
            if (doc.type === 'file') {
                await previewDocument(node);
            } else {
                // 如果是文件夹，只显示信息
                showFolderInfo(doc);
            }
            
        } else {
            const errorMsg = result.error || '未知错误';
            throw new Error(errorMsg);
        }
    } catch (error) {
        console.error('showDocumentDetail error:', error);
        showError('获取文档详情失败: ' + error.message);
        
        // 重置到空状态
        showEmptyState();
    }
}

function updatePreviewTitle(doc) {
    try {
        const previewTitle = document.getElementById('previewTitle');
        if (!previewTitle) {
            console.error('previewTitle element not found');
            return;
        }
        
        const icon = doc.type === 'folder' ? 'bi-folder icon-folder' : getFileIcon(doc.file_type);
        
        previewTitle.innerHTML = `
            <i class="bi ${icon}"></i>
            ${doc.name || '未知文档'}
        `;
    } catch (error) {
        console.error('updatePreviewTitle error:', error);
    }
}

function showPreviewActions(doc) {
    try {
        const previewActions = document.getElementById('previewActions');
        const downloadBtn = document.getElementById('downloadBtn');
        const editBtn = document.getElementById('editBtn');
        const deleteBtn = document.getElementById('deleteBtn');
        const vectorizeBtn = document.getElementById('vectorizeBtn');
        
        if (!previewActions) {
            console.error('previewActions element not found');
            return;
        }
        
        // 显示操作按钮
        previewActions.style.display = 'flex';
        
        // 根据文档类型调整按钮显示
        if (doc.type === 'file') {
            if (downloadBtn) downloadBtn.style.display = 'flex';
            if (vectorizeBtn) {
                vectorizeBtn.style.display = 'flex';
                
                // 更新向量化按钮状态
                if (doc.is_vectorized) {
                    vectorizeBtn.innerHTML = `
                        <i class="bi bi-vector-pen"></i>
                        查看向量化
                    `;
                } else {
                    vectorizeBtn.innerHTML = `
                        <i class="bi bi-vector-pen"></i>
                        向量化
                    `;
                }
            }
        } else {
            if (downloadBtn) downloadBtn.style.display = 'none';
            if (vectorizeBtn) vectorizeBtn.style.display = 'none';
        }
        
        // 编辑和删除按钮始终显示
        if (editBtn) editBtn.style.display = 'flex';
        if (deleteBtn) deleteBtn.style.display = 'flex';
    } catch (error) {
        console.error('showPreviewActions error:', error);
    }
}

function showFolderInfo(doc) {
    const previewContent = document.getElementById('previewContent');
    previewContent.innerHTML = `
        <div class="empty-state">
            <i class="bi bi-folder icon-folder" style="font-size: 48px;"></i>
            <h4>${doc.name}</h4>
            <p>这是一个文件夹</p>
            <small class="text-muted">选择文件夹中的文件进行预览</small>
        </div>
    `;
}

// ============ 预览操作按钮功能 ============

function downloadCurrentDocument() {
    if (currentPreviewDocument && currentPreviewDocument.type === 'file') {
        downloadDocument(currentPreviewDocument.id, currentPreviewDocument.name);
    }
}

function editCurrentDocument() {
    if (currentPreviewDocument) {
        editDocument(
            currentPreviewDocument.id, 
            currentPreviewDocument.name, 
            currentPreviewDocument.description || '', 
            currentPreviewDocument.type
        );
    }
}

function deleteCurrentDocument() {
    if (currentPreviewDocument) {
        deleteDocument(currentPreviewDocument.id);
    }
}

function toggleVectorization() {
    if (currentPreviewDocument && currentPreviewDocument.type === 'file') {
        if (vectorizationMode) {
            closeVectorization();
        } else {
            showVectorization(currentPreviewDocument.id);
        }
    }
}

// ============ 向量化功能 ============

async function showVectorization(docId) {
    vectorizationMode = true;
    
    // 调整布局
    const documentPreviewPanel = document.getElementById('documentPreviewPanel');
    const vectorizationPanel = document.getElementById('vectorizationPanel');
    const vectorizeBtn = document.getElementById('vectorizeBtn');
    
    // 预览面板收缩到50%
    documentPreviewPanel.classList.add('vectorization-active');
    
    // 显示向量化面板
    vectorizationPanel.classList.add('active');
    
    // 更新向量化按钮状态
    vectorizeBtn.classList.add('active');
    vectorizeBtn.innerHTML = `
        <i class="bi bi-vector-pen"></i>
        关闭向量化
    `;
    
    // 显示配置区域和操作按钮
    document.getElementById('vectorizationConfig').style.display = 'block';
    document.getElementById('vectorPanelFooter').style.display = 'block';
    document.getElementById('vectorEmptyState').style.display = 'none';
    
    // 存储当前文档ID
    vectorizationPanel.dataset.currentDocId = docId;
    
    // 加载向量化信息
    await loadVectorizationInfo(docId);
}

function closeVectorization() {
    vectorizationMode = false;
    
    // 恢复布局
    const documentPreviewPanel = document.getElementById('documentPreviewPanel');
    const vectorizationPanel = document.getElementById('vectorizationPanel');
    const vectorizeBtn = document.getElementById('vectorizeBtn');
    
    // 恢复预览面板原始宽度
    documentPreviewPanel.classList.remove('vectorization-active');
    
    // 隐藏向量化面板
    vectorizationPanel.classList.remove('active');
    
    // 隐藏配置区域和操作按钮
    document.getElementById('vectorizationConfig').style.display = 'none';
    document.getElementById('vectorPanelFooter').style.display = 'none';
    document.getElementById('vectorEmptyState').style.display = 'block';
    
    // 恢复向量化按钮状态
    if (vectorizeBtn) {
        vectorizeBtn.classList.remove('active');
        if (currentPreviewDocument && currentPreviewDocument.is_vectorized) {
            vectorizeBtn.innerHTML = `
                <i class="bi bi-vector-pen"></i>
                查看向量化
            `;
        } else {
            vectorizeBtn.innerHTML = `
                <i class="bi bi-vector-pen"></i>
                向量化
            `;
        }
    }
}

// ============ 向量化信息加载 ============

async function loadVectorizationInfo(docId) {
    const vectorDiv = document.getElementById('vectorPanelContent');
    const chunksContainer = vectorDiv.querySelector('#vectorChunksContainer');
    
    // 如果没有chunks容器，创建一个
    if (!chunksContainer) {
        const newContainer = document.createElement('div');
        newContainer.id = 'vectorChunksContainer';
        newContainer.className = 'vector-chunks-container';
        vectorDiv.appendChild(newContainer);
    }
    
    // 显示加载状态
    const container = document.getElementById('vectorChunksContainer');
    container.innerHTML = '<div class="text-center p-3"><div class="loading"></div><p>正在加载向量信息...</p></div>';
    
    try {
        // 获取配置参数
        const chunkSize = parseInt(document.getElementById('sideChunkSize').value) || 1000;
        const overlap = parseInt(document.getElementById('sideChunkOverlap').value) || 200;
        
        // 预览向量化信息
        const response = await fetch(`/api/vectorize/preview/${docId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chunk_size: chunkSize,
                overlap: overlap
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            displayVectorChunks(result.data.chunks);
            // 存储向量化数据
            const vectorizationPanel = document.getElementById('vectorizationPanel');
            vectorizationPanel.dataset.vectorizationData = JSON.stringify(result.data);
        } else {
            throw new Error(result.error);
        }
    } catch (error) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="bi bi-exclamation-triangle text-warning"></i>
                <p>无法加载向量信息: ${error.message}</p>
                <button class="btn btn-sm btn-primary mt-2" onclick="loadVectorizationInfo(${docId})">
                    <i class="bi bi-arrow-clockwise"></i> 重新加载
                </button>
            </div>
        `;
    }
}

function displayVectorChunks(chunks) {
    const container = document.getElementById('vectorChunksContainer');
    
    if (!chunks || chunks.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <i class="bi bi-info-circle"></i>
                <p>暂无向量分段信息</p>
            </div>
        `;
        return;
    }
    
    let chunksHtml = `
        <div class="vector-chunks-header mb-3">
            <h6><i class="bi bi-puzzle"></i> 文档分段 (${chunks.length}个)</h6>
        </div>
    `;
    
    chunks.forEach((chunk, index) => {
        const content = chunk.content || chunk;
        chunksHtml += `
            <div class="vector-chunk-item" data-chunk-id="${chunk.id || index}">
                <div class="vector-chunk-header">
                    <span class="vector-chunk-index">分段 ${index + 1}</span>
                </div>
                <div class="vector-chunk-content" id="chunk-content-${index}">
                    <textarea class="form-control chunk-textarea" rows="3" data-chunk-index="${index}" style="font-size: 12px;">${content}</textarea>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = chunksHtml;
}

// ============ 已移除的模式切换功能 ============

function switchToSearchMode() {
    // 已合并到统一界面，保留空函数以防报错
}

function switchToManageMode() {
    // 已合并到统一界面，保留空函数以防报错
}

function showManageEmptyState() {
    // 已合并到统一界面，保留空函数以防报错
}

function showDocumentDetailInManageMode(node) {
    // 重定向到统一的文档详情显示
    showDocumentDetail(node);
}

async function loadFilePreviewAndVectorInfo(doc) {
    // 这个函数的功能已经合并到showDocumentDetail中
}

function showCompactDocumentDetail(doc) {
    // 已不再需要压缩版本，使用统一的显示方式
    showDocumentInfoPanel(doc);
}

// ============ 文档树管理功能 ============

async function loadFileTree() {
    try {
        const response = await fetch('/api/documents/tree');
        const result = await response.json();
        
        if (result.success) {
            renderFileTree(result.data);
        } else {
            showError('加载文档树失败: ' + result.error);
        }
    } catch (error) {
        showError('加载文档树失败: ' + error.message);
    }
}

function renderFileTree(nodes) {
    const fileTree = document.getElementById('fileTree');
    
    // 清除现有内容
    fileTree.innerHTML = '';
    
    if (!nodes || nodes.length === 0) {
        fileTree.innerHTML = `
            <div class="empty-state">
                <i class="bi bi-folder2-open"></i>
                <h5>暂无文档</h5>
                <p>点击上方按钮开始添加文档</p>
            </div>
        `;
        return;
    }

    // 构建节点映射表
    buildNodeMap(nodes);
    
    // 渲染树结构
    nodes.forEach(node => {
        const nodeElement = createTreeNode(node, 0);
        fileTree.appendChild(nodeElement);
    });
    
    // 添加点击空白区域取消选中的事件监听器
    fileTree.addEventListener('click', function(e) {
        // 如果点击的是文档树容器本身（空白区域），则取消选中
        if (e.target === fileTree || e.target.classList.contains('empty-state') || 
            e.target.closest('.empty-state')) {
            clearSelection();
        }
    });
}

// 递归构建节点映射
function buildNodeMap(nodeList) {
    nodeList.forEach(node => {
        nodeMap[node.id] = node;
        if (node.children && node.children.length > 0) {
            buildNodeMap(node.children);
        }
    });
}

function createTreeNode(node, level) {
    const div = document.createElement('div');
    div.className = 'tree-node';
    
    // 展开按钮 - 默认展开状态显示向下箭头
    let expandButton = '';
    if (node.children && node.children.length > 0) {
        expandButton = `<button class="tree-expand-btn expanded" onclick="toggleTreeNode(this, event)">
            <i class="bi bi-chevron-down"></i>
        </button>`;
    }
    
    // 文件图标和类型
    const icon = getFileIcon(node.type === 'folder' ? 'folder' : node.file_type);
    const iconClass = node.type === 'folder' ? 'icon-folder' : 
                     icon.includes('file-earmark-pdf') ? 'icon-pdf' :
                     icon.includes('file-earmark-word') ? 'icon-word' :
                     icon.includes('file-earmark-excel') ? 'icon-excel' :
                     icon.includes('file-earmark-image') ? 'icon-image' :
                     icon.includes('camera-video') ? 'icon-video' : 'icon-file';
    
    const item = document.createElement('div');
    item.className = `tree-item ${node.children && node.children.length > 0 ? 'has-children' : ''}`;
    item.dataset.nodeId = node.id;
    item.dataset.nodeType = node.type;
    item.dataset.nodeName = node.name; // 添加节点名称用于搜索
    
    // 将标签信息存储到dataset中用于搜索
    if (node.tags && node.tags.length > 0) {
        const tagNames = node.tags.map(tag => tag.name).join('|');
        item.dataset.nodeTags = tagNames;
    } else {
        item.dataset.nodeTags = '';
    }
    
    // 显示文件大小（仅对文件显示）
    let sizeInfo = '';
    if (node.type !== 'folder' && node.file_size) {
        sizeInfo = `<span class="tree-item-size">${formatFileSize(node.file_size)}</span>`;
    }
    
    // 显示标签
    const tagsHtml = renderNodeTags(node.tags || []);
    
    item.innerHTML = `
        ${expandButton}
        <div class="tree-item-content">
            <i class="bi ${icon} ${iconClass}"></i>
            <span class="tree-item-text">${node.name}</span>
            ${tagsHtml}
            ${sizeInfo}
        </div>
    `;
    
    item.addEventListener('click', function(e) {
        e.stopPropagation();
        
        // 如果点击的是已选中的节点，则取消选中
        if (selectedNode && selectedNode.id === node.id) {
            clearSelection();
        } else {
            selectNode(node);
        }
    });
    
    // 添加右键菜单
    item.addEventListener('contextmenu', function(e) {
        e.preventDefault();
        showContextMenu(e, node);
    });
    
    div.appendChild(item);
    
    // 递归添加子节点
    if (node.children && node.children.length > 0) {
        const childrenContainer = document.createElement('div');
        childrenContainer.className = 'tree-children'; // 默认展开，不添加 collapsed 类
        
        node.children.forEach(child => {
            const childElement = createTreeNode(child, level + 1);
            childrenContainer.appendChild(childElement);
        });
        
        div.appendChild(childrenContainer);
    }
    
    return div;
}

function selectNode(node) {
    // 清除之前的选择状态
    clearTreeSelection();
    
    // 设置选中状态
    selectedNode = node;
    const nodeElement = document.querySelector(`[data-node-id="${node.id}"]`);
    if (nodeElement) {
        nodeElement.classList.add('selected');
    }
    
    // 设置上传父目录ID
    if (node.type === 'folder') {
        // 如果选中的是文件夹，则上传到该文件夹内
        currentParentId = node.id;
    } else {
        // 如果选中的是文件，则上传到其父文件夹
        currentParentId = node.parent_id;
    }
    
    // 更新路径显示
    updateSelectedPath();
    
    // 显示文档详情
    showDocumentDetail(node);
}

// 恢复选中的节点状态（用于文档树重新加载后）
function restoreSelectedNode(nodeId) {
    try {
        // 从节点映射中查找节点
        const node = nodeMap[nodeId];
        if (node) {
            // 重新选中节点
            selectNode(node);
            
            // 确保父节点展开，使选中的节点可见
            expandParentNodes(document.querySelector(`[data-node-id="${nodeId}"]`)?.closest('.tree-node'));
            
            console.log('已恢复选中状态:', node.name);
        } else {
            console.warn('无法找到要恢复的节点:', nodeId);
            // 如果找不到节点，重置选中状态
            clearTreeSelection();
            currentParentId = null;
        }
    } catch (error) {
        console.error('恢复选中状态时出错:', error);
        clearTreeSelection();
        currentParentId = null;
    }
}

function clearTreeSelection() {
    document.querySelectorAll('.tree-item.selected').forEach(item => {
        item.classList.remove('selected');
    });
    selectedNode = null;
    currentPreviewDocument = null;
    // 清除选择时重置为根目录上传
    currentParentId = null;
}

// 新增：清除选择函数
function clearSelection() {
    // 清除树选择状态
    clearTreeSelection();
    
    // 更新路径显示
    updateSelectedPath();
    
    // 显示空状态
    showEmptyState();
    
    // 关闭向量化面板（如果打开）
    closeVectorization();
    
    // 显示成功提示
    console.log('已取消选择');
}

// 新增：更新选中路径显示
function updateSelectedPath() {
    const pathText = document.getElementById('pathText');
    const pathClear = document.getElementById('pathClear');
    
    if (selectedNode) {
        // 构建文件路径
        const path = buildNodePath(selectedNode);
        pathText.textContent = path;
        pathClear.style.display = 'inline-block';
    } else {
        pathText.textContent = '未选择任何文件';
        pathClear.style.display = 'none';
    }
}

// 新增：构建节点路径
function buildNodePath(node) {
    const pathParts = [];
    let currentNode = node;
    
    // 递归向上查找父节点，构建路径
    while (currentNode) {
        pathParts.unshift(currentNode.name);
        
        // 查找父节点
        if (currentNode.parent_id) {
            currentNode = findNodeById(currentNode.parent_id);
        } else {
            currentNode = null;
        }
    }
    
    return pathParts.join(' / ');
}

// 新增：在当前文档树数据中查找节点
function findNodeById(nodeId) {
    return nodeMap[nodeId] || null;
}

// ============ 文档详情显示 ============
// 函数已在上面定义，此处为占位注释

// ============ 搜索功能 ============

function initSearchInput() {
    const treeSearch = document.getElementById('treeSearch');
    
    // 文档树搜索
    treeSearch.addEventListener('input', function(e) {
        filterDocumentTree(e.target.value);
    });
}

async function performSemanticSearch() {
    // 这个函数现在由聊天功能处理，保留为兼容性
    // 移除了顶部搜索框，所以这个函数不再需要
    console.log('Semantic search moved to chat interface');
}

function formatSearchResults(results, query, similarityLevel, minScore) {
    const similarityLabels = {
        'high': '高相关性 (≥60%)',
        'medium': '中等相关性 (≥30%)', 
        'low': '低相关性 (≥10%)',
        'any': '显示所有结果'
    };
    
    const levelText = similarityLabels[similarityLevel] || '中等相关性';
    
    let message = `找到了 ${results.length} 个相关结果 (${levelText})：\n\n`;
    
    results.forEach((result, index) => {
        const score = (result.score * 100).toFixed(1);
        message += `${index + 1}. **${result.document.name}** (相关度: ${score}%)\n`;
        message += `${result.text.substring(0, 100)}...\n\n`;
    });
    
    message += `✨ 提示：点击文档名称可以查看完整内容预览。`;
    if (similarityLevel !== 'any') {
        message += `<br>💡 如需更多结果，可降低相关性要求后重新搜索。`;
    }
    
    return message.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

function displaySearchResults(data, query) {
    const resultsDiv = document.getElementById('searchResults');
    
    if (!data.results || data.results.length === 0) {
        resultsDiv.innerHTML = `
            <div class="empty-state">
                <i class="bi bi-search"></i>
                <h4>没有找到相关结果</h4>
                <p>尝试使用其他关键词搜索</p>
            </div>
        `;
        return;
    }
    
    let resultsHtml = `
        <div class="search-header">
            <h3 class="search-title">搜索结果</h3>
            <div class="search-info">
                找到 <strong>${data.results.length}</strong> 个相关结果，关键词: "<strong>${query}</strong>"
            </div>
        </div>
    `;
    
    data.results.forEach(result => {
        resultsHtml += `
            <div class="result-item" onclick="selectDocumentFromSearch(${result.document.id})">
                <div class="result-header">
                    <h5 class="result-title">
                        <i class="bi ${getFileIcon(result.document.file_type)}"></i>
                        ${result.document.name}
                    </h5>
                    <span class="result-score">${(result.score * 100).toFixed(1)}%</span>
                </div>
                <div class="result-content">${result.text}</div>
                <div class="result-meta">
                    <span><i class="bi bi-file-text"></i> 类型: ${result.document.file_type}</span>
                    <span><i class="bi bi-hash"></i> 分段: ${result.chunk_index || 'N/A'}</span>
                    <span><i class="bi bi-calendar"></i> ${formatDateTime(result.document.created_at)}</span>
                </div>
            </div>
        `;
    });
    
    resultsDiv.innerHTML = resultsHtml;
}

function selectDocumentFromSearch(docId) {
    // 在树中选择对应节点
    const nodeElement = document.querySelector(`[data-node-id="${docId}"]`);
    if (nodeElement) {
        clearTreeSelection();
        nodeElement.classList.add('selected');
        
        // 获取节点数据并显示详情
        fetch(`/api/documents/${docId}/detail`)
            .then(response => response.json())
            .then(result => {
                if (result.success) {
                    selectedNode = result.data;
                    showDocumentDetail(result.data);
                }
            });
    }
}

// ============ 右键菜单功能 ============

function showContextMenu(event, node) {
    const contextMenu = document.getElementById('contextMenu');
    
    // 设置菜单位置
    contextMenu.style.left = event.pageX + 'px';
    contextMenu.style.top = event.pageY + 'px';
    contextMenu.style.display = 'block';
    
    // 设置选中的节点
    selectedNode = node;
    
    // 点击其他地方隐藏菜单
    document.addEventListener('click', hideContextMenu, { once: true });
}

function hideContextMenu() {
    document.getElementById('contextMenu').style.display = 'none';
}

function editSelectedDocument() {
    if (selectedNode) {
        editDocument(selectedNode.id, selectedNode.name, selectedNode.description || '', selectedNode.type);
    }
    hideContextMenu();
}

function vectorizeSelectedDocument() {
    if (selectedNode && selectedNode.type === 'file') {
        vectorizeDocument(selectedNode.id);
    }
    hideContextMenu();
}

function deleteSelectedDocument() {
    if (selectedNode) {
        deleteDocument(selectedNode.id);
    }
    hideContextMenu();
}

function downloadSelectedDocument() {
    if (selectedNode && selectedNode.type === 'file') {
        downloadDocument(selectedNode.id, selectedNode.name);
    }
    hideContextMenu();
}

// ============ 文档管理操作 ============

// 上传文件相关功能
function initUploadArea() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const folderInput = document.getElementById('folderInput');
    
    if (!uploadArea || !fileInput || !folderInput) {
        console.warn('Upload area elements not found, skipping initialization');
        return;
    }
    
    // 检查是否已经初始化过（通过自定义属性标记）
    if (uploadArea.dataset.initialized === 'true') {
        console.log('Upload area already initialized, skipping');
        return;
    }
    
    // 上传类型切换事件监听器
    document.querySelectorAll('input[name="uploadType"]').forEach(radio => {
        // 移除可能存在的旧事件监听器
        radio.removeEventListener('change', updateUploadAreaDisplay);
        radio.addEventListener('change', updateUploadAreaDisplay);
    });
    
    // 上传区域点击事件
    uploadArea.addEventListener('click', function(e) {
        // 如果点击的是重新选择按钮，不处理
        if (e.target.closest('.btn-reset-files')) {
            return;
        }
        
        const uploadType = document.querySelector('input[name="uploadType"]:checked').value;
        if (uploadType === 'folder') {
            folderInput.click();
        } else {
            fileInput.click();
        }
    });
    
    // 文件选择事件
    fileInput.addEventListener('change', function(e) {
        e.stopPropagation(); // 防止事件冒泡
        selectedFiles = Array.from(e.target.files);
        updateUploadAreaDisplay();
    });
    
    folderInput.addEventListener('change', function(e) {
        e.stopPropagation(); // 防止事件冒泡
        selectedFiles = Array.from(e.target.files);
        updateUploadAreaDisplay();
        showFileListPreview();
    });
    
    // 拖拽支持
    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('dragover');
    });
    
    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('dragover');
    });
    
    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        e.stopPropagation(); // 防止事件冒泡
        uploadArea.classList.remove('dragover');
        
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            selectedFiles = files;
            updateUploadAreaDisplay();
            if (files.length > 1) {
                showFileListPreview();
            }
        }
    });
    
    // 标记为已初始化
    uploadArea.dataset.initialized = 'true';
    console.log('Upload area initialized successfully');
}

function updateUploadAreaDisplay() {
    const uploadArea = document.getElementById('uploadArea');
    const uploadTypeElement = document.querySelector('input[name="uploadType"]:checked');
    
    // 添加空值检查
    if (!uploadArea) {
        console.warn('uploadArea element not found');
        return;
    }
    
    if (!uploadTypeElement) {
        console.warn('uploadType radio button not found');
        return;
    }
    
    const uploadType = uploadTypeElement.value;
    
    if (selectedFiles.length > 0) {
        const totalSize = selectedFiles.reduce((sum, file) => sum + file.size, 0);
        const isFolder = uploadType === 'folder' || selectedFiles.length > 1;
        
        uploadArea.innerHTML = `
            <i class="bi ${isFolder ? 'bi-folder-check' : 'bi-file-check'}" style="font-size: 3rem; color: #28a745;"></i>
            <h5 class="mt-3 text-success">已选择${isFolder ? '文件夹' : '文件'}</h5>
            <p class="mb-2"><strong>${selectedFiles.length}</strong> 个文件</p>
            <p class="text-muted">总大小: ${formatFileSize(totalSize)}</p>
            <button type="button" class="btn btn-sm btn-outline-secondary btn-reset-files" onclick="event.stopPropagation(); clearSelectedFiles();">
                <i class="bi bi-x-circle"></i> 重新选择
            </button>
        `;
    } else {
        const isFolder = uploadType === 'folder';
        uploadArea.innerHTML = `
            <i class="bi bi-cloud-upload" style="font-size: 3rem; color: #6c757d;"></i>
            <h5 class="mt-3">${isFolder ? '拖拽文件夹到此处或点击选择文件夹' : '拖拽文件到此处或点击选择文件'}</h5>
            <p class="text-muted">${isFolder ? '支持整个文件夹上传，保持目录结构' : '支持 PDF, Word, Excel, 图片, 视频文件'}</p>
        `;
    }
}

function showFileListPreview() {
    const previewDiv = document.getElementById('fileListPreview');
    const fileListDiv = document.getElementById('fileList');
    
    if (selectedFiles.length === 0) {
        previewDiv.style.display = 'none';
        return;
    }
    
    const totalSize = selectedFiles.reduce((sum, file) => sum + file.size, 0);
    document.getElementById('fileCount').textContent = selectedFiles.length;
    document.getElementById('totalSize').textContent = formatFileSize(totalSize);
    
    fileListDiv.innerHTML = '';
    
    // 检查是否是文件夹上传（通过检查文件是否有webkitRelativePath）
    const isFromFolder = selectedFiles.some(file => file.webkitRelativePath);
    
    // 如果是文件夹上传，需要显示文件夹结构
    if (isFromFolder) {
        // 构建文件夹树结构
        const folderTree = buildFolderTree(selectedFiles);
        
        // 递归渲染文件夹树
        renderFolderTreeRecursive(folderTree, fileListDiv, 0);
    } else {
        // 单个文件上传，保持原有逻辑
        selectedFiles.forEach(file => {
            const item = document.createElement('div');
            item.className = 'list-group-item d-flex justify-content-between align-items-center';
            item.innerHTML = `
                <div>
                    <i class="bi ${getFileIconForName(file.name)}"></i>
                    <span class="ms-2">${file.name}</span>
                </div>
                <small class="text-muted">${formatFileSize(file.size)}</small>
            `;
            fileListDiv.appendChild(item);
        });
    }
    
    previewDiv.style.display = 'block';
}

// 新函数：构建文件夹树结构
function buildFolderTree(files) {
    const tree = {};
    
    files.forEach(file => {
        const relativePath = file.webkitRelativePath || file.name;
        const pathParts = relativePath.split('/');
        
        let currentLevel = tree;
        
        // 遍历路径的每一部分
        for (let i = 0; i < pathParts.length; i++) {
            const part = pathParts[i];
            
            if (i === pathParts.length - 1) {
                // 这是文件
                currentLevel[part] = {
                    type: 'file',
                    size: file.size,
                    file: file,
                    name: part
                };
            } else {
                // 这是文件夹
                if (!currentLevel[part]) {
                    currentLevel[part] = {
                        type: 'folder',
                        name: part,
                        children: {}
                    };
                }
                currentLevel = currentLevel[part].children;
            }
        }
    });
    
    return tree;
}

// 新函数：递归渲染文件夹树
function renderFolderTreeRecursive(tree, container, level) {
    // 获取当前层级的所有项目
    const items = Object.keys(tree).map(key => ({
        key: key,
        ...tree[key]
    }));
    
    // 排序：文件夹优先，然后按名称排序
    items.sort((a, b) => {
        if (a.type !== b.type) {
            return a.type === 'folder' ? -1 : 1;
        }
        return a.name.localeCompare(b.name);
    });
    
    // 渲染每个项目
    items.forEach(item => {
        const itemElement = document.createElement('div');
        itemElement.className = 'list-group-item d-flex justify-content-between align-items-center';
        
        const indent = '&nbsp;'.repeat(level * 4);
        let icon, sizeText;
        
        if (item.type === 'folder') {
            icon = 'bi-folder';
            sizeText = '';
        } else {
            icon = getFileIconForName(item.name);
            sizeText = formatFileSize(item.size);
        }
        
        itemElement.innerHTML = `
            <div>
                ${indent}<i class="bi ${icon}"></i>
                <span class="ms-2">${item.name}</span>
            </div>
            <small class="text-muted">${sizeText}</small>
        `;
        
        container.appendChild(itemElement);
        
        // 如果是文件夹，递归渲染子项目
        if (item.type === 'folder' && item.children) {
            renderFolderTreeRecursive(item.children, container, level + 1);
        }
    });
}

function clearSelectedFiles() {
    selectedFiles = [];
    
    // 添加空值检查，防止元素不存在时出错
    const fileInput = document.getElementById('fileInput');
    const folderInput = document.getElementById('folderInput');
    const fileListPreview = document.getElementById('fileListPreview');
    
    if (fileInput) {
        fileInput.value = '';
    }
    if (folderInput) {
        folderInput.value = '';
    }
    if (fileListPreview) {
        fileListPreview.style.display = 'none';
    }
    
    updateUploadAreaDisplay();
}

// 模态框显示函数
function showUploadModal() {
    try {
        const modal = new bootstrap.Modal(document.getElementById('uploadModal'));
        
        // 添加空值检查
        const fileDescription = document.getElementById('fileDescription');
        const uploadProgress = document.getElementById('uploadProgress');
        
        if (fileDescription) {
            fileDescription.value = '';
        }
        
        if (uploadProgress) {
            uploadProgress.style.display = 'none';
        }
        
        clearSelectedFiles();
        clearTagSelection('upload'); // 清空上传标签选择
        updateUploadAreaDisplay();
        modal.show();
    } catch (error) {
        console.error('打开上传模态框时出错:', error);
        showError('无法打开上传文件对话框');
    }
}

function showCreateFolderModal() {
    const modal = new bootstrap.Modal(document.getElementById('createFolderModal'));
    document.getElementById('folderName').value = '';
    document.getElementById('folderDescription').value = '';
    clearTagSelection('folder'); // 清空文件夹标签选择
    modal.show();
}

// 具体操作函数
async function uploadFile() {
    if (selectedFiles.length === 0) {
        showError('请选择要上传的文件');
        return;
    }
    
    const description = document.getElementById('fileDescription').value.trim();
    const uploadType = document.querySelector('input[name="uploadType"]:checked').value;
    
    // 保存当前选中的节点ID，以便上传后恢复选中状态
    const previousSelectedNodeId = selectedNode ? selectedNode.id : null;
    
    try {
        document.getElementById('uploadProgress').style.display = 'block';
        document.getElementById('uploadBtn').disabled = true;
        
        if (uploadType === 'folder' || selectedFiles.length > 1) {
            await uploadBatch(selectedFiles, description);
        } else {
            await uploadSingleFile(selectedFiles[0], description);
        }
        
        showSuccess('文件上传成功');
        bootstrap.Modal.getInstance(document.getElementById('uploadModal')).hide();
        
        // 清空标签选择
        clearTagSelection('upload');
        
        // 重新加载文档树和统计信息
        await loadFileTree();
        loadStats();
        
        // 恢复之前选中的节点状态
        if (previousSelectedNodeId) {
            setTimeout(() => {
                restoreSelectedNode(previousSelectedNodeId);
            }, 100); // 给DOM更新一点时间
        }
        
    } catch (error) {
        showError('上传失败: ' + error.message);
    } finally {
        document.getElementById('uploadProgress').style.display = 'none';
        document.getElementById('uploadBtn').disabled = false;
    }
}

async function uploadSingleFile(file, description) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('description', description);
    if (currentParentId) {
        formData.append('parent_id', currentParentId);
    }
    
    // 添加标签数据
    const tagIds = getTagIds(selectedUploadTags);
    if (tagIds.length > 0) {
        formData.append('tag_ids', tagIds.join(','));
    }
    
    const response = await fetch('/api/upload/', {
        method: 'POST',
        body: formData
    });
    
    const result = await response.json();
    if (!result.success) {
        throw new Error(result.error);
    }
}

async function uploadBatch(files, description) {
    const formData = new FormData();
    
    files.forEach(file => formData.append('files', file));
    files.forEach(file => {
        const relativePath = file.webkitRelativePath || file.name;
        formData.append('file_paths[]', relativePath);
    });
    
    formData.append('description', description);
    if (currentParentId) {
        formData.append('parent_id', currentParentId);
    }
    
    // 添加标签数据
    const tagIds = getTagIds(selectedUploadTags);
    if (tagIds.length > 0) {
        formData.append('tag_ids', tagIds.join(','));
    }
    
    const response = await fetch('/api/upload/batch', {
        method: 'POST',
        body: formData
    });
    
    const result = await response.json();
    if (!result.success) {
        throw new Error(result.error);
    }
}

async function createFolder() {
    const name = document.getElementById('folderName').value.trim();
    const description = document.getElementById('folderDescription').value.trim();
    
    if (!name) {
        showError('请输入文件夹名称');
        return;
    }
    
    // 保存当前选中的节点ID，以便创建文件夹后恢复选中状态
    const previousSelectedNodeId = selectedNode ? selectedNode.id : null;
    
    try {
        const requestData = { name, description };
        if (currentParentId !== null) {
            requestData.parent_id = currentParentId;
        }
        
        // 添加标签数据
        const tagIds = getTagIds(selectedFolderTags);
        if (tagIds.length > 0) {
            requestData.tag_ids = tagIds;
        }
        
        const response = await fetch('/api/documents/folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('文件夹创建成功');
            bootstrap.Modal.getInstance(document.getElementById('createFolderModal')).hide();
            
            // 清空标签选择
            clearTagSelection('folder');
            
            // 重新加载文档树
            await loadFileTree();
            
            // 恢复之前选中的节点状态
            if (previousSelectedNodeId) {
                setTimeout(() => {
                    restoreSelectedNode(previousSelectedNodeId);
                }, 100); // 给DOM更新一点时间
            }
        } else {
            showError('创建文件夹失败: ' + result.error);
        }
    } catch (error) {
        showError('创建文件夹失败: ' + error.message);
    }
}

function editDocument(docId, name, description, type) {
    document.getElementById('editDocumentId').value = docId;
    document.getElementById('editDocumentName').value = name;
    document.getElementById('editDocumentDescription').value = description || '';
    
    // 加载文档的标签信息
    if (selectedNode && selectedNode.tags) {
        setEditTags(selectedNode.tags);
    } else {
        clearTagSelection('edit');
    }
    
    const title = type === 'folder' ? '编辑文件夹' : '编辑文件';
    document.getElementById('editDocumentTitle').innerHTML = 
        `<i class="bi bi-pencil me-2"></i>${title}`;
    
    const modal = new bootstrap.Modal(document.getElementById('editDocumentModal'));
    modal.show();
}

async function updateDocument() {
    const docId = document.getElementById('editDocumentId').value;
    const name = document.getElementById('editDocumentName').value.trim();
    const description = document.getElementById('editDocumentDescription').value.trim();
    
    if (!name) {
        showError('名称不能为空');
        return;
    }
    
    // 保存当前选中的节点ID，以便更新后恢复选中状态
    const previousSelectedNodeId = selectedNode ? selectedNode.id : null;
    
    try {
        // 准备更新数据，包含标签
        const updateData = { 
            name, 
            description,
            tag_ids: getTagIds(selectedEditTags)
        };
        
        const response = await fetch(`/api/documents/${docId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('更新成功');
            bootstrap.Modal.getInstance(document.getElementById('editDocumentModal')).hide();
            
            // 清空标签选择
            clearTagSelection('edit');
            
            // 重新加载文档树
            await loadFileTree();
            
            // 恢复之前选中的节点状态
            if (previousSelectedNodeId) {
                setTimeout(() => {
                    restoreSelectedNode(previousSelectedNodeId);
                }, 100); // 给DOM更新一点时间
            }
        } else {
            showError('更新失败: ' + result.error);
        }
    } catch (error) {
        showError('更新失败: ' + error.message);
    }
}

async function deleteDocument(docId) {
    try {
        // 获取文档详情以确定类型
        const doc = currentPreviewDocument || selectedNode;
        const isFolder = doc && doc.type === 'folder';
        
        let confirmMessage, confirmTitle;
        
        if (isFolder) {
            confirmMessage = `
                <div class="alert alert-warning mb-3">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    <strong>注意：</strong>删除文件夹将同时删除该文件夹下的所有文件和子文件夹！
                </div>
                <p>确定要删除文件夹 "<strong>${doc.name}</strong>" 及其所有内容吗？</p>
                <small class="text-muted">此操作不可撤销，请谨慎操作。</small>
            `;
            confirmTitle = '删除文件夹确认';
        } else {
            confirmMessage = `
                确定要删除文件 "<strong>${doc ? doc.name : '此文档'}</strong>" 吗？
                <br><br><small class="text-muted">此操作不可撤销</small>
            `;
            confirmTitle = '删除文件确认';
        }
        
        const confirmed = await showConfirmModal(
            confirmMessage,
            confirmTitle,
            '删除',
            'btn-danger'
        );
        
        if (!confirmed) return;
        
        const response = await fetch(`/api/documents/${docId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess(isFolder ? '文件夹删除成功' : '文件删除成功');
            loadFileTree();
            loadStats();
            clearTreeSelection();
            
            // 重置预览状态
            showEmptyState();
        } else {
            showError('删除失败: ' + result.error);
        }
    } catch (error) {
        showError('删除失败: ' + error.message);
    }
}

// ============ 向量化功能 ============

async function vectorizeDocument(docId) {
    try {
        // 检查向量化状态
        const statusResponse = await fetch(`/api/vectorize/status/${docId}`);
        const statusResult = await statusResponse.json();
        
        if (statusResult.success) {
            const status = statusResult.data;
            
            if (!status.is_supported) {
                showError('此文件类型不支持向量化');
                return;
            }
            
            if (status.is_vectorized) {
                const confirmed = await showConfirmModal(
                    '此文档已经向量化过，是否重新处理？',
                    '重新向量化',
                    '确认',
                    'btn-warning'
                );
                if (!confirmed) return;
            }
        }
        
        // 预览文档内容
        const previewResponse = await fetch(`/api/vectorize/preview/${docId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chunk_size: 1000,
                overlap: 200
            })
        });
        
        const previewResult = await previewResponse.json();
        
        if (previewResult.success) {
            showVectorizationModal(previewResult.data);
        } else {
            showError('获取文档预览失败: ' + previewResult.error);
        }
        
    } catch (error) {
        showError('启动向量化失败: ' + error.message);
    }
}

function showVectorizationModal(data) {
    const modal = new bootstrap.Modal(document.getElementById('vectorizationModal'));
    
    // 设置基本信息
    document.getElementById('vectorizationDocName').textContent = data.document_name;
    document.getElementById('vectorizationChunkCount').textContent = data.chunk_count;
    document.getElementById('vectorizationTextLength').textContent = data.text_length;
    
    // 设置分段参数
    document.getElementById('chunkSize').value = data.chunk_size;
    document.getElementById('chunkOverlap').value = data.overlap;
    
    // 渲染文本分段
    renderTextChunks(data.chunks);
    
    // 存储数据
    document.getElementById('vectorizationModal').dataset.documentId = data.document_id;
    document.getElementById('vectorizationModal').dataset.originalData = JSON.stringify(data);
    
    modal.show();
}

function renderTextChunks(chunks) {
    const container = document.getElementById('chunksContainer');
    container.innerHTML = '';
    
    if (!chunks || !Array.isArray(chunks)) {
        container.innerHTML = '<div class="alert alert-warning">没有可显示的文本分段</div>';
        return;
    }
    
    chunks.forEach((chunk, index) => {
        const content = chunk && chunk.content !== undefined ? chunk.content : '';
        const chunkId = chunk && chunk.id ? chunk.id : `chunk_${index}`;
        
        const chunkDiv = document.createElement('div');
        chunkDiv.className = 'mb-3';
        chunkDiv.innerHTML = `
            <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                    <h6 class="mb-0">分段 ${index + 1}</h6>
                    <span class="badge bg-secondary">${content.length} 字符</span>
                </div>
                <div class="card-body">
                    <textarea 
                        class="form-control chunk-textarea" 
                        rows="4" 
                        data-chunk-id="${chunkId}"
                        placeholder="文本内容..."
                    >${content}</textarea>
                </div>
            </div>
        `;
        container.appendChild(chunkDiv);
    });
}

async function rechunkText() {
    try {
        const modal = document.getElementById('vectorizationModal');
        const documentId = modal.dataset.documentId;
        const chunkSize = parseInt(document.getElementById('chunkSize').value) || 1000;
        const overlap = parseInt(document.getElementById('chunkOverlap').value) || 200;
        
        showInfo('正在重新分段，请稍候...');
        
        const response = await fetch(`/api/vectorize/preview/${documentId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chunk_size: chunkSize,
                overlap: overlap
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            renderTextChunks(result.data.chunks);
            document.getElementById('vectorizationChunkCount').textContent = result.data.chunk_count;
            showSuccess('重新分段完成');
        } else {
            showError('重新分段失败: ' + result.error);
        }
    } catch (error) {
        showError('重新分段失败: ' + error.message);
    }
}

async function executeVectorization() {
    try {
        const modal = document.getElementById('vectorizationModal');
        const documentId = modal.dataset.documentId;
        
        // 收集编辑后的文本块
        const chunks = [];
        const textareas = modal.querySelectorAll('.chunk-textarea');
        
        textareas.forEach((textarea, index) => {
            const content = textarea.value.trim();
            if (content) {
                chunks.push({
                    id: textarea.dataset.chunkId,
                    content: content
                });
            }
        });
        
        if (chunks.length === 0) {
            showWarning('没有可向量化的文本内容');
            return;
        }
        
        const executeBtn = document.getElementById('executeVectorization');
        executeBtn.disabled = true;
        executeBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 向量化中...';
        
        showInfo('正在执行向量化，请稍候...');
        
        const response = await fetch(`/api/vectorize/execute/${documentId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chunks })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess(`向量化完成！已处理 ${result.data.vectorized_chunks || chunks.length} 个文本块`);
            bootstrap.Modal.getInstance(modal).hide();
            
            // 更新当前预览文档的向量化状态
            updateVectorizationStatus(documentId, true, result.data.vectorized_at);
            
            if (selectedNode) {
                await showDocumentDetail(selectedNode);
            }
            loadStats();
        } else {
            showError('向量化失败: ' + result.error);
        }
    } catch (error) {
        showError('向量化失败: ' + error.message);
    } finally {
        const executeBtn = document.getElementById('executeVectorization');
        executeBtn.disabled = false;
        executeBtn.innerHTML = '<i class="bi bi-check"></i> 确认向量化';
    }
}

// ============ 工具函数 ============

async function loadStats() {
    try {
        const response = await fetch('/api/search/stats');
        const result = await response.json();
        
        if (result.success) {
            const stats = result.data;
            document.getElementById('totalDocs').textContent = stats.document_stats.total_documents;
            document.getElementById('totalFolders').textContent = stats.document_stats.total_folders;
            document.getElementById('totalVectors').textContent = stats.vector_stats.total_entities || 0;
        }
    } catch (error) {
        console.error('加载统计信息失败:', error);
    }
}

function filterDocumentTree(searchTerm) {
    const treeItems = document.querySelectorAll('.tree-item');
    const searchClear = document.getElementById('searchClear');
    
    if (searchTerm) {
        searchClear.style.display = 'block';
    } else {
        searchClear.style.display = 'none';
    }
    
    // 清除之前的高亮
    clearSearchHighlight();
    
    if (!searchTerm) {
        // 显示所有项目
        document.querySelectorAll('.tree-node').forEach(node => {
            node.style.display = 'block';
        });
        return;
    }
    
    const searchTermLower = searchTerm.toLowerCase();
    let hasVisibleItems = false;
    
    // 检测搜索类型
    let isTagSearch = false;
    let tagSearchTerm = '';
    let nameSearchTerm = '';
    
    // 解析搜索语法
    if (searchTerm.includes('tag:')) {
        // 支持标签搜索语法：tag:标签名
        const tagMatch = searchTerm.match(/tag:([^\s]+)/);
        if (tagMatch) {
            isTagSearch = true;
            tagSearchTerm = tagMatch[1].toLowerCase();
            // 移除tag:部分，保留其他搜索词用于文件名搜索
            nameSearchTerm = searchTerm.replace(/tag:[^\s]+/g, '').trim().toLowerCase();
        }
    } else {
        // 普通搜索，同时搜索文件名和标签
        nameSearchTerm = searchTermLower;
    }
    
    // 首先隐藏所有节点
    document.querySelectorAll('.tree-node').forEach(node => {
        node.style.display = 'none';
    });
    
    // 收集所有匹配的节点
    const matchingNodes = [];
    treeItems.forEach(item => {
        const nodeName = item.dataset.nodeName || '';
        const nodeTags = item.dataset.nodeTags || '';
        
        let matches = false;
        let matchType = '';
        
        if (isTagSearch) {
            // 标签搜索模式
            const tagMatches = nodeTags.toLowerCase().includes(tagSearchTerm);
            const nameMatches = nameSearchTerm ? nodeName.toLowerCase().includes(nameSearchTerm) : true;
            
            if (tagMatches && nameMatches) {
                matches = true;
                matchType = tagMatches ? 'tag' : 'name';
            }
        } else {
            // 普通搜索模式 - 在文件名和标签中都搜索
            const nameMatches = nodeName.toLowerCase().includes(nameSearchTerm);
            const tagMatches = nodeTags.toLowerCase().includes(nameSearchTerm);
            
            if (nameMatches || tagMatches) {
                matches = true;
                matchType = nameMatches ? 'name' : 'tag';
            }
        }
        
        if (matches) {
            matchingNodes.push(item);
            item.classList.add('search-match');
            item.dataset.matchType = matchType;
            
            // 高亮搜索结果
            if (matchType === 'name') {
                highlightSearchTerm(item, isTagSearch && nameSearchTerm ? nameSearchTerm : searchTerm);
            } else if (matchType === 'tag') {
                highlightTagMatch(item, isTagSearch ? tagSearchTerm : nameSearchTerm);
            }
            
            hasVisibleItems = true;
        } else {
            item.classList.remove('search-match');
            delete item.dataset.matchType;
        }
    });
    
    // 显示匹配的节点及其所有父节点
    matchingNodes.forEach(item => {
        const treeNode = item.closest('.tree-node');
        showNodeAndParents(treeNode);
    });
    
    // 如果没有匹配项，显示提示
    if (!hasVisibleItems) {
        showNoSearchResults(searchTerm, isTagSearch);
    }
}

function highlightSearchTerm(item, searchTerm) {
    const textSpan = item.querySelector('.tree-item-text');
    const originalText = item.dataset.nodeName;
    const searchTermLower = searchTerm.toLowerCase();
    const originalTextLower = originalText.toLowerCase();
    
    const index = originalTextLower.indexOf(searchTermLower);
    if (index !== -1 && textSpan) {
        const beforeMatch = originalText.substring(0, index);
        const match = originalText.substring(index, index + searchTerm.length);
        const afterMatch = originalText.substring(index + searchTerm.length);
        
        textSpan.innerHTML = `${beforeMatch}<span class="highlight">${match}</span>${afterMatch}`;
    }
}

function highlightTagMatch(item, searchTerm) {
    const tagElements = item.querySelectorAll('.node-tag');
    const searchTermLower = searchTerm.toLowerCase();
    
    tagElements.forEach(tagElement => {
        const tagText = tagElement.textContent || '';
        const tagTextLower = tagText.toLowerCase();
        
        if (tagTextLower.includes(searchTermLower)) {
            const index = tagTextLower.indexOf(searchTermLower);
            if (index !== -1) {
                const beforeMatch = tagText.substring(0, index);
                const match = tagText.substring(index, index + searchTerm.length);
                const afterMatch = tagText.substring(index + searchTerm.length);
                
                tagElement.innerHTML = `${beforeMatch}<span class="highlight">${match}</span>${afterMatch}`;
                tagElement.classList.add('tag-search-match');
            }
        }
    });
}

function clearSearchHighlight() {
    document.querySelectorAll('.tree-item').forEach(item => {
        const textSpan = item.querySelector('.tree-item-text');
        const originalText = item.dataset.nodeName;
        if (originalText && textSpan) {
            textSpan.textContent = originalText;
        }
        item.classList.remove('search-match');
        delete item.dataset.matchType;
        
        // 清除标签高亮
        const tagElements = item.querySelectorAll('.node-tag');
        tagElements.forEach(tagElement => {
            const originalTagText = tagElement.dataset.originalText || tagElement.textContent;
            tagElement.textContent = originalTagText;
            tagElement.classList.remove('tag-search-match');
            tagElement.dataset.originalText = originalTagText; // 保存原始文本以备后用
        });
    });
}

function expandParentNodes(node) {
    let currentNode = node;
    while (currentNode) {
        const parentNode = currentNode.parentElement.closest('.tree-node');
        if (parentNode) {
            const expandBtn = parentNode.querySelector('.tree-expand-btn');
            const childrenContainer = parentNode.querySelector('.tree-children');
            
            if (expandBtn && childrenContainer && childrenContainer.classList.contains('collapsed')) {
                childrenContainer.classList.remove('collapsed');
                expandBtn.classList.add('expanded');
                expandBtn.querySelector('i').className = 'bi bi-chevron-down';
            }
        }
        currentNode = parentNode;
    }
}

function showNoSearchResults(searchTerm, isTagSearch) {
    // 在文档树区域显示搜索提示
    const fileTree = document.getElementById('fileTree') || document.querySelector('.file-tree');
    if (fileTree) {
        const existingNoResults = fileTree.querySelector('.no-search-results');
        if (existingNoResults) {
            existingNoResults.remove();
        }
        
        const noResultsDiv = document.createElement('div');
        noResultsDiv.className = 'no-search-results text-center p-4';
        
        let hintMessage = '';
        if (isTagSearch) {
            hintMessage = `
                <div class="mb-3">
                    <i class="bi bi-search text-muted" style="font-size: 2rem;"></i>
                </div>
                <h6 class="text-muted">未找到标签匹配结果</h6>
                <p class="text-muted small mb-2">搜索词: "${searchTerm}"</p>
                <div class="text-muted small">
                    <p>搜索提示:</p>
                    <ul class="list-unstyled">
                        <li>• 使用 <code>tag:标签名</code> 搜索特定标签</li>
                        <li>• 使用 <code>tag:重要 文档名</code> 组合搜索</li>
                        <li>• 直接输入关键词搜索文件名和标签</li>
                    </ul>
                </div>
            `;
        } else {
            hintMessage = `
                <div class="mb-3">
                    <i class="bi bi-search text-muted" style="font-size: 2rem;"></i>
                </div>
                <h6 class="text-muted">未找到匹配结果</h6>
                <p class="text-muted small mb-2">搜索词: "${searchTerm}"</p>
                <div class="text-muted small">
                    <p>搜索提示:</p>
                    <ul class="list-unstyled">
                        <li>• 尝试使用其他关键词</li>
                        <li>• 使用 <code>tag:标签名</code> 搜索标签</li>
                        <li>• 检查拼写是否正确</li>
                    </ul>
                </div>
            `;
        }
        
        noResultsDiv.innerHTML = hintMessage;
        fileTree.appendChild(noResultsDiv);
    }
    
    console.log(`没有找到匹配的文档: ${searchTerm} (${isTagSearch ? '标签搜索' : '普通搜索'})`);
}

function clearTreeSearch() {
    document.getElementById('treeSearch').value = '';
    document.getElementById('searchClear').style.display = 'none';
    clearSearchHighlight();
    document.querySelectorAll('.tree-node').forEach(node => {
        node.style.display = 'block';
    });
    
    // 清除搜索提示
    const fileTree = document.getElementById('fileTree') || document.querySelector('.file-tree');
    if (fileTree) {
        const noResults = fileTree.querySelector('.no-search-results');
        if (noResults) {
            noResults.remove();
        }
    }
}

function getFileIcon(fileType) {
    const icons = {
        'folder': 'bi-folder-fill icon-folder',
        'pdf': 'bi-file-earmark-pdf icon-pdf',
        'word': 'bi-file-earmark-word icon-word',
        'excel': 'bi-file-earmark-excel icon-excel',
        'image': 'bi-file-earmark-image icon-image',
        'video': 'bi-file-earmark-play icon-video'
    };
    return icons[fileType] || 'bi-file-earmark icon-file';
}

function getFileIconForName(fileName) {
    const ext = fileName.split('.').pop().toLowerCase();
    const iconMap = {
        'pdf': 'bi-file-earmark-pdf icon-pdf',
        'doc': 'bi-file-earmark-word icon-word',
        'docx': 'bi-file-earmark-word icon-word',
        'xls': 'bi-file-earmark-excel icon-excel',
        'xlsx': 'bi-file-earmark-excel icon-excel',
        'jpg': 'bi-file-earmark-image icon-image',
        'jpeg': 'bi-file-earmark-image icon-image',
        'png': 'bi-file-earmark-image icon-image',
        'gif': 'bi-file-earmark-image icon-image'
    };
    return iconMap[ext] || 'bi-file-earmark icon-file';
}

function formatFileSize(bytes) {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDateTime(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleString('zh-CN');
}

function formatExcelSheetData(sheetData) {
    if (!sheetData || !Array.isArray(sheetData) || sheetData.length === 0) {
        return '<p class="text-muted">无数据</p>';
    }
    
    let tableHtml = '<div class="table-responsive"><table class="table table-bordered table-sm">';
    
    // 处理表头
    if (sheetData.length > 0) {
        tableHtml += '<thead class="table-light"><tr>';
        const firstRow = sheetData[0];
        if (Array.isArray(firstRow)) {
            firstRow.forEach((cell, index) => {
                const cellValue = cell !== null && cell !== undefined ? String(cell) : '';
                tableHtml += `<th scope="col">${cellValue || `列${index + 1}`}</th>`;
            });
        }
        tableHtml += '</tr></thead>';
    }
    
    // 处理数据行
    tableHtml += '<tbody>';
    sheetData.slice(1).forEach((row, rowIndex) => {
        if (Array.isArray(row)) {
            tableHtml += '<tr>';
            row.forEach(cell => {
                const cellValue = cell !== null && cell !== undefined ? String(cell) : '';
                tableHtml += `<td>${cellValue}</td>`;
            });
            tableHtml += '</tr>';
        }
    });
    tableHtml += '</tbody></table></div>';
    
    return tableHtml;
}

// ============ 通知系统 ============

function showToast(message, type = 'success', duration = 3000) {
    const toastContainer = document.getElementById('toastContainer');
    const toastId = 'toast-' + Date.now();
    
    const icons = {
        'success': 'bi-check-circle-fill',
        'error': 'bi-x-circle-fill',
        'warning': 'bi-exclamation-triangle-fill',
        'info': 'bi-info-circle-fill'
    };
    
    const titles = {
        'success': '成功',
        'error': '错误',
        'warning': '警告',
        'info': '信息'
    };
    
    const toastHTML = `
        <div id="${toastId}" class="toast ${type}" role="alert">
            <div class="toast-header">
                <i class="toast-icon ${icons[type]}"></i>
                <strong class="me-auto">${titles[type]}</strong>
                <button type="button" class="btn-close" onclick="hideToast('${toastId}')"></button>
            </div>
            <div class="toast-body">${message}</div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    
    const toastElement = document.getElementById(toastId);
    toastElement.classList.add('show');
    
    setTimeout(() => hideToast(toastId), duration);
    
    return toastId;
}

function hideToast(toastId) {
    const toastElement = document.getElementById(toastId);
    if (toastElement) {
        toastElement.classList.remove('show');
        toastElement.classList.add('hide');
        setTimeout(() => toastElement.remove(), 300);
    }
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showError(message) {
    showToast(message, 'error', 5000);
}

function showWarning(message) {
    showToast(message, 'warning', 4000);
}

function showInfo(message) {
    showToast(message, 'info');
}

// ============ 确认对话框 ============

let confirmModalCallback = null;

function showConfirmModal(message, title = '确认操作', confirmText = '确定', confirmClass = 'btn-danger') {
    return new Promise((resolve) => {
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
        
        document.getElementById('confirmModalTitle').innerHTML = `
            <i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>${title}
        `;
        document.getElementById('confirmModalMessage').innerHTML = message;
        
        const confirmBtn = document.getElementById('confirmModalBtn');
        confirmBtn.textContent = confirmText;
        confirmBtn.className = `btn ${confirmClass}`;
        
        confirmModalCallback = resolve;
        modal.show();
    });
}

function confirmModalAction() {
    if (confirmModalCallback) {
        confirmModalCallback(true);
        confirmModalCallback = null;
    }
    bootstrap.Modal.getInstance(document.getElementById('confirmModal')).hide();
}

// 监听确认模态框关闭
document.getElementById('confirmModal').addEventListener('hidden.bs.modal', function() {
    if (confirmModalCallback) {
        confirmModalCallback(false);
        confirmModalCallback = null;
    }
});

// ============ 文档树展开/折叠功能 ============

function toggleTreeNode(button, event) {
    event.stopPropagation();
    
    const treeNode = button.closest('.tree-node');
    const childrenContainer = treeNode.querySelector('.tree-children');
    const icon = button.querySelector('i');
    
    if (childrenContainer) {
        if (childrenContainer.classList.contains('collapsed')) {
            // 展开 - 右箭头向下旋转
            childrenContainer.classList.remove('collapsed');
            button.classList.add('expanded');
            icon.className = 'bi bi-chevron-down';
        } else {
            // 折叠 - 右箭头向右
            childrenContainer.classList.add('collapsed');
            button.classList.remove('expanded');
            icon.className = 'bi bi-chevron-right';
        }
    }
}

// ============ 文档预览功能 ============

async function previewDocument(node) {
    if (!node || node.type !== 'file') {
        return;
    }
    
    currentPreviewDocument = node;
    
    // 更新预览标题 - 只显示文件名和图标，不要下载按钮
    document.getElementById('previewTitle').innerHTML = `
        <i class="bi ${getFileIcon(node.file_type)}"></i>
        ${node.name}
    `;
    
    const previewContent = document.getElementById('previewContent');
    
    // 显示加载状态
    previewContent.innerHTML = `
        <div class="preview-main-content">
            <div class="loading-placeholder">
                <div class="loading"></div>
                <p>正在加载预览...</p>
            </div>
        </div>
    `;
    
    try {
        // 根据文件类型调用不同的预览API
        let response;
        const fileType = node.file_type.toLowerCase();
        
        if (fileType === 'pdf') {
            // 对于PDF，直接显示原文件
            previewContent.innerHTML = `
                <div class="pdf-container" style="flex: 1; margin-bottom: 15px;">
                    <iframe src="/api/preview/pdf/raw/${node.id}" 
                            style="width: 100%; height: 450px; border: none; border-radius: 4px;" 
                            title="PDF预览 - ${node.name}">
                        <p>您的浏览器不支持PDF预览。<a href="/api/documents/${node.id}/download">点击下载查看</a></p>
                    </iframe>
                </div>
                <div class="document-info-section">
                    ${generateDocumentInfo(node)}
                </div>
            `;
            return;
        } else if (['word', 'doc', 'docx'].includes(fileType)) {
            // 对于Word文档，使用API获取提取的文本内容
            response = await fetch(`/api/preview/word/${node.id}`);
        } else if (['excel', 'xls', 'xlsx'].includes(fileType)) {
            // 对于Excel文档，默认显示数据预览，提供原文件下载选项
            response = await fetch(`/api/preview/excel/${node.id}`);
        } else if (['image', 'jpg', 'jpeg', 'png', 'gif', 'bmp'].includes(fileType)) {
            // 对于图片，直接显示
            previewContent.innerHTML = `
                <div class="text-center" style="flex: 1; margin-bottom: 15px;">
                    <img src="/api/preview/image/${node.id}" class="img-fluid" alt="${node.name}" 
                         style="max-height: 350px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                </div>
                <div class="document-info-section">
                    ${generateDocumentInfo(node)}
                </div>
            `;
            return;
        } else if (['video', 'mp4', 'avi', 'mov', 'wmv', 'mkv', 'flv', 'webm'].includes(fileType)) {
            // 对于视频，直接显示视频播放器
            previewContent.innerHTML = `
                <div class="text-center" style="flex: 1; margin-bottom: 15px;">
                    <video controls style="max-width: 100%; max-height: 350px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
                        <source src="/api/preview/video/${node.id}" type="video/${fileType === 'video' ? 'mp4' : fileType}">
                        您的浏览器不支持视频播放。
                    </video>
                </div>
                <div class="document-info-section">
                    ${generateDocumentInfo(node)}
                </div>
            `;
            return;
        } else {
            previewContent.innerHTML = `
                <div class="empty-state" style="margin-bottom: 15px;">
                    <i class="bi bi-file-earmark"></i>
                    <h5>暂不支持预览</h5>
                    <p>此文件类型暂不支持在线预览</p>
                    <small class="text-muted">文件类型: ${fileType}</small>
                </div>
                <div class="document-info-section">
                    ${generateDocumentInfo(node)}
                </div>
            `;
            return;
        }
        
        const result = await response.json();
        
        if (result.success) {
            displayPreviewContent(result.data, fileType, node);
        } else {
            previewContent.innerHTML = `
                <div class="empty-state" style="margin-bottom: 15px;">
                    <i class="bi bi-exclamation-triangle text-warning"></i>
                    <h5>预览失败</h5>
                    <p>${result.error}</p>
                </div>
                <div class="document-info-section">
                    ${generateDocumentInfo(node)}
                </div>
            `;
        }
    } catch (error) {
        previewContent.innerHTML = `
            <div class="empty-state" style="margin-bottom: 15px;">
                <i class="bi bi-exclamation-triangle text-danger"></i>
                <h5>预览出错</h5>
                <p>${error.message}</p>
            </div>
            <div class="document-info-section">
                ${generateDocumentInfo(node)}
            </div>
        `;
    }
}

// ============ 新增：生成文档信息 ============

function generateDocumentInfo(node) {
    const createdDate = node.created_at ? formatDateTime(node.created_at) : '未知';
    const updatedDate = node.updated_at ? formatDateTime(node.updated_at) : '未知';
    const fileSize = node.file_size ? formatFileSize(node.file_size) : '未知';
    const fileType = node.file_type || '未知';
    const description = node.description || '无描述';
    const isVectorized = node.is_vectorized ? '是' : '否';
    const vectorizedDate = node.vectorized_at ? formatDateTime(node.vectorized_at) : '';
    
    return `
        <div class="document-info-horizontal" style="background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 8px; padding: 12px; margin-top: 10px;">
            <div style="display: flex; flex-wrap: wrap; gap: 20px; align-items: center; font-size: 13px;">
                <div style="display: flex; align-items: center; gap: 6px;">
                    <i class="bi bi-file-earmark text-primary" style="font-size: 14px;"></i>
                    <span style="font-weight: 500; color: #495057;">${node.name}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <i class="bi bi-tag text-secondary" style="font-size: 12px;"></i>
                    <span style="color: #6c757d;">${fileType}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <i class="bi bi-archive text-secondary" style="font-size: 12px;"></i>
                    <span style="color: #6c757d;">${fileSize}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <i class="bi bi-vector-pen ${isVectorized === '是' ? 'text-success' : 'text-muted'}" style="font-size: 12px;"></i>
                    <span style="color: ${isVectorized === '是' ? '#28a745' : '#6c757d'};" title="${vectorizedDate ? '向量化时间: ' + vectorizedDate : ''}">向量化: ${isVectorized}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <i class="bi bi-calendar text-secondary" style="font-size: 12px;"></i>
                    <span style="color: #6c757d;">${createdDate}</span>
                </div>
            </div>
            ${description !== '无描述' ? `
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e9ecef;">
                <div style="display: flex; align-items: flex-start; gap: 6px;">
                    <i class="bi bi-chat-square-text text-secondary" style="font-size: 12px; margin-top: 2px;"></i>
                    <span style="color: #6c757d; font-size: 12px; line-height: 1.4;">${description}</span>
                </div>
            </div>
            ` : ''}
        </div>
    `;
}

function displayPreviewContent(data, fileType, node) {
    const previewContent = document.getElementById('previewContent');
    
    if (fileType === 'word' || fileType === 'doc' || fileType === 'docx') {
        // Word文档预览处理
        const content = data.content || data.text || '';
        if (content) {
            previewContent.innerHTML = `
                <div class="office-content" style="flex: 1; margin-bottom: 15px;">
                    <div class="text-preview-info mb-3">
                        <p class="mb-1"><strong>文档内容:</strong></p>
                        <p class="mb-0 text-muted">Word文档文本预览</p>
                    </div>
                    <div class="text-content-preview">
                        <div class="card">
                            <div class="card-body">
                                <div class="text-content" style="white-space: pre-wrap; line-height: 1.6; font-size: 14px;">
                                    ${content.replace(/\n/g, '<br>')}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="document-info-section">
                    ${generateDocumentInfo(node)}
                </div>
            `;
        } else {
            previewContent.innerHTML = `
                <div class="office-content" style="flex: 1; margin-bottom: 15px;">
                    <div class="text-preview-info mb-3">
                        <p class="mb-0 text-muted">Word文档预览</p>
                    </div>
                    <div class="empty-state">
                        <i class="bi bi-file-earmark-word"></i>
                        <h5>Word文档</h5>
                        <p>无法提取文档内容或文档为空</p>
                    </div>
                </div>
                <div class="document-info-section">
                    ${generateDocumentInfo(node)}
                </div>
            `;
        }
    } else if (fileType === 'excel' || fileType === 'xls' || fileType === 'xlsx') {
        // Excel预览处理
        if (data.sheets && data.sheets.length > 0) {
            let sheetsHtml = '';
            data.sheets.forEach((sheet, index) => {
                sheetsHtml += `
                    <div class="excel-sheet mb-4">
                        <h6 class="sheet-title">
                            <i class="bi bi-table me-2"></i>
                            工作表: ${sheet.name || `Sheet${index + 1}`}
                        </h6>
                        <div class="excel-data-content">
                            ${formatExcelSheetData(sheet.data)}
                        </div>
                    </div>
                `;
            });
            
            previewContent.innerHTML = `
                <div class="office-content" style="flex: 1; margin-bottom: 15px;">
                    <div class="text-preview-info mb-3">
                        <p class="mb-1"><strong>工作表数量:</strong> ${data.sheets.length}</p>
                        <p class="mb-0 text-muted">Excel数据预览</p>
                    </div>
                    ${sheetsHtml}
                </div>
                <div class="document-info-section">
                    ${generateDocumentInfo(node)}
                </div>
            `;
        } else {
            previewContent.innerHTML = `
                <div class="office-content" style="flex: 1; margin-bottom: 15px;">
                    <div class="text-preview-info mb-3">
                        <p class="mb-0 text-muted">Excel文档预览</p>
                    </div>
                    <div class="empty-state">
                        <i class="bi bi-table"></i>
                        <h5>Excel文档</h5>
                        <p>无法读取工作表数据</p>
                    </div>
                </div>
                <div class="document-info-section">
                    ${generateDocumentInfo(node)}
                </div>
            `;
        }
    }
}

// ============ 聊天功能 ============

function initChatInput() {
    const chatInput = document.getElementById('chatInput');
    const sendButton = document.getElementById('sendButton');
    
    // 回车键发送
    chatInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });
    
    // 点击发送按钮
    sendButton.addEventListener('click', sendChatMessage);
}

async function sendChatMessage() {
    const chatInput = document.getElementById('chatInput');
    const similarityLevel = document.getElementById('similarityLevel');
    const message = chatInput.value.trim();
    
    if (!message) {
        return;
    }
    
    // 获取用户选择的相似度等级
    const selectedSimilarity = similarityLevel ? similarityLevel.value : 'medium';
    
    // 获取LLM配置
    const llmConfig = getLLMConfig();
    
    // 添加用户消息到聊天记录
    addChatMessage('user', message);
    chatInput.value = '';
    
    // 智能选择搜索策略并显示提示
    const searchStrategy = determineSearchStrategy(message, selectedSimilarity);
    showSearchStrategyHint(searchStrategy, message);
    
    // 显示AI正在思考的状态
    const thinkingId = addChatMessage('assistant', '', true);
    
    try {
        // 构建请求数据
        const requestData = {
            query: message,
            top_k: 5,
            similarity_level: selectedSimilarity,
            llm_model: llmConfig.model,
            enable_llm: llmConfig.isAvailable
        };
        
        let response;
        if (searchStrategy === 'hybrid') {
            // 使用混合搜索
            response = await fetch('/api/search/hybrid', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
        } else {
            // 使用纯语义搜索
            response = await fetch('/api/search/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
        }
        
        const result = await response.json();
        
        // 移除thinking消息
        removeChatMessage(thinkingId);
        
        // 隐藏搜索策略提示
        hideSearchStrategyHint();
        
        if (result.success && (
            (result.data.file_results && result.data.file_results.length > 0) || 
            (result.data.results && result.data.results.length > 0)
        )) {
            // 如果有LLM答案，先显示LLM答案
            if (result.data.llm_info && result.data.llm_info.answer) {
                const llmMessage = formatLLMAnswer(result.data.llm_info.answer, result.data.llm_info);
                addChatMessage('assistant', llmMessage);
            }
            
            // 显示搜索结果（优先使用文件级别结果）
            const resultMessage = formatFileSearchResults(result.data, message);
            addChatMessage('assistant', resultMessage);
            
            // 如果有搜索结果，自动预览第一个文档
            const fileResults = result.data.file_results || result.data.results;
            if (fileResults && fileResults.length > 0) {
                const firstFile = fileResults[0];
                const document = firstFile.document || firstFile.document;
                if (document) {
                    highlightDocumentInTree(document.id);
                    previewDocument(document);
                }
            }
        } else {
            // 智能提示用户如何优化搜索
            const suggestionMessage = generateSearchSuggestions(message, selectedSimilarity, searchStrategy);
            addChatMessage('assistant', suggestionMessage);
        }
    } catch (error) {
        // 确保在任何错误情况下都移除thinking消息
        removeChatMessage(thinkingId);
        hideSearchStrategyHint();
        addChatMessage('assistant', '搜索时出现错误，请稍后再试。');
        console.error('Chat search error:', error);
    }
}

function determineSearchStrategy(query, similarityLevel) {
    // 智能确定搜索策略
    
    // 如果查询包含专业术语、缩写、数字等，优先使用混合搜索
    const hasSpecialTerms = /[A-Z]{2,}|[a-zA-Z]+\d+|\d{2,}|[a-zA-Z]{2,4}/.test(query);
    
    // 如果查询很短（少于4个字符）或包含特殊术语，使用混合搜索
    if (query.length <= 4 || hasSpecialTerms) {
        return 'hybrid';
    }
    
    // 如果相似度要求是高相关性，但查询较短，也使用混合搜索
    if (similarityLevel === 'high' && query.length <= 6) {
        return 'hybrid';
    }
    
    // 其他情况使用语义搜索
    return 'semantic';
}

// LLM答案格式化函数
function formatLLMAnswer(llmAnswer, llmInfo) {
    let message = `<div class="llm-answer-container">
        <div class="llm-answer-header">
            <i class="bi bi-robot"></i> <strong>AI智能分析</strong>`;
    
    // 显示LLM处理状态
    if (llmInfo) {
        message += `<div class="llm-status">`;
        if (llmInfo.query_optimized) {
            message += `<span class="llm-status-item optimization"><i class="bi bi-lightbulb"></i> 查询优化</span>`;
        }
        if (llmInfo.reranked) {
            message += `<span class="llm-status-item rerank"><i class="bi bi-sort-down"></i> 结果重排序</span>`;
        }
        if (llmInfo.used) {
            message += `<span class="llm-status-item answer"><i class="bi bi-chat-square-text"></i> 智能答案</span>`;
        }
        if (llmInfo.model) {
            message += `<span class="llm-status-item model"><i class="bi bi-cpu"></i> ${llmInfo.model}</span>`;
        }
        message += `</div>`;
    }
    
    message += `</div>
        <div class="llm-answer-content">
            ${escapeHtml(llmAnswer).replace(/\n/g, '<br>')}
        </div>
    </div>`;
    
    return message;
}

// HTML转义函数
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatFileSearchResults(data, query) {
    // 文件级别搜索结果格式化（支持超链接）
    
    const similarityLabels = {
        'high': '高相关性 (≥60%)',
        'medium': '中等相关性 (≥30%)', 
        'low': '低相关性 (≥10%)',
        'any': '显示所有结果'
    };
    
    const levelText = similarityLabels[data.similarity_level] || '中等相关性';
    const searchType = data.search_type || 'semantic';
    
    let searchTypeText = '';
    if (searchType === 'hybrid') {
        searchTypeText = ` (智能混合搜索: ${data.semantic_count || 0}个语义 + ${data.keyword_count || 0}个关键词)`;
    }
    
    // 显示查询优化信息
    let optimizationInfo = '';
    if (data.llm_info && data.llm_info.query_optimized && data.llm_info.original_query) {
        optimizationInfo = `<div class="query-optimization-info">
            <i class="bi bi-lightbulb text-warning"></i> 
            <small>查询已优化：${escapeHtml(data.llm_info.original_query)} → ${escapeHtml(data.llm_info.optimized_query || query)}</small>
        </div>`;
    }
    
    // 优先使用file_results，回退到results
    const fileResults = data.file_results || data.results;
    const resultCount = data.total_files || fileResults.length;
    
    let message = optimizationInfo + `📁 找到了 ${resultCount} 个相关文件 (${levelText})${searchTypeText}：\n\n`;
    
    fileResults.forEach((fileResult, index) => {
        const document = fileResult.document;
        const score = (fileResult.score * 100).toFixed(1);
        
        // 确定搜索类型图标
        const searchTypes = fileResult.search_types || [fileResult.search_type] || ['semantic'];
        const searchIcon = searchTypes.includes('hybrid') ? '🧠' : 
                          searchTypes.includes('keyword') ? '🔤' : '🎯';
        
        // 显示重排序标记
        let rerankMark = '';
        if (data.llm_info && data.llm_info.reranked) {
            rerankMark = ' <span class="rerank-indicator">🔄</span>';
        }
        
        // 创建可点击的文件链接
        const fileName = escapeHtml(document.name);
        const fileLink = `<a href="#" class="file-link" onclick="selectFileFromChat(${document.id}); return false;" title="点击定位并预览文件">${fileName}</a>`;
        
        message += `${index + 1}. ${searchIcon} **${fileLink}** (${score}%)${rerankMark}\n`;
        
        // 显示文件信息
        if (document.file_type) {
            message += `   📄 类型: ${document.file_type.toUpperCase()}`;
        }
        if (fileResult.chunk_count) {
            message += ` | 📊 匹配片段: ${fileResult.chunk_count}个`;
        }
        message += `\n`;
        
        // 显示匹配的内容预览
        if (fileResult.chunks && fileResult.chunks.length > 0) {
            const topChunk = fileResult.chunks[0];
            let displayText = topChunk.text ? topChunk.text.substring(0, 100) : '';
            
            // 高亮匹配的关键词（如果有）
            if (topChunk.matched_keywords && topChunk.matched_keywords.length > 0) {
                topChunk.matched_keywords.forEach(keyword => {
                    const regex = new RegExp(`(${keyword})`, 'gi');
                    displayText = displayText.replace(regex, '**$1**');
                });
            }
            
            message += `   💬 内容摘要: ${displayText}...\n`;
        }
        
        message += `\n`;
    });
    
    message += `✨ 提示：点击文件名可自动定位到文档树并预览内容。`;
    if (data.similarity_level !== 'any') {
        message += `<br>💡 如需更多结果，可降低相关性要求后重新搜索。`;
    }
    
    return message.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

function formatSearchResultsEnhanced(data, query) {
    // 兼容旧版本的搜索结果格式化（向后兼容）
    return formatFileSearchResults(data, query);
}

function generateSearchSuggestions(query, similarityLevel, searchStrategy) {
    // 生成搜索建议
    
    const similarityLabels = {
        'high': '高相关性',
        'medium': '中等相关性', 
        'low': '低相关性',
        'any': '所有结果'
    };
    
    const levelText = similarityLabels[similarityLevel] || '中等相关性';
    const strategyText = searchStrategy === 'hybrid' ? '智能混合搜索' : '语义搜索';
    
    let suggestions = `🤔 在${levelText}(${strategyText})要求下，没有找到相关的文档内容。\n\n`;
    
    suggestions += `**优化建议：**\n`;
    
    if (similarityLevel === 'high') {
        suggestions += `1. 🎯 降低相关性要求（选择"中等"或"低相关性"）\n`;
    }
    
    if (query.length <= 4) {
        suggestions += `2. 📝 尝试使用更完整的词汇或短语\n`;
        suggestions += `3. 🔤 添加相关的上下文词汇\n`;
    }
    
    if (searchStrategy === 'semantic') {
        suggestions += `4. 🧠 系统已自动尝试智能搜索，如仍无结果可能文档未向量化\n`;
    }
    
    suggestions += `5. 📚 检查是否有相关文档已上传并向量化\n`;
    suggestions += `6. 🔄 尝试使用同义词或相关术语重新搜索\n`;
    
    // 根据查询内容给出具体建议
    if (/[A-Z]{2,}/.test(query)) {
        suggestions += `\n💡 **专业术语提示：** 检测到您搜索的是专业缩写，建议：\n`;
        suggestions += `- 尝试搜索完整术语名称\n`;
        suggestions += `- 添加相关描述词汇\n`;
    }
    
    return suggestions.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

function addChatMessage(sender, content, isThinking = false) {
    const chatMessages = document.getElementById('chatMessages');
    const messageId = 'msg-' + Date.now();
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    messageDiv.id = messageId;
    
    if (isThinking) {
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="loading"></div>
                <span class="ms-2">正在搜索...</span>
            </div>
        `;
    } else {
        const time = new Date().toLocaleTimeString();
        messageDiv.innerHTML = `
            <div class="message-content">
                <div>${content}</div>
                <div class="message-time">${time}</div>
            </div>
        `;
    }
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageId;
}

function removeChatMessage(messageId) {
    const message = document.getElementById(messageId);
    if (message) {
        message.remove();
    }
}

function formatSearchResults(results, query) {
    let message = `找到了 ${results.length} 个相关结果：\n\n`;
    
    results.forEach((result, index) => {
        const score = (result.score * 100).toFixed(1);
        message += `${index + 1}. **${result.document.name}** (相关度: ${score}%)\n`;
        message += `${result.text.substring(0, 100)}...\n\n`;
    });
    
    message += `✨ 提示：点击文档名称可以查看完整内容预览。`;
    
    return message.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

function highlightDocumentInTree(docId) {
    // 清除之前的高亮
    document.querySelectorAll('.tree-item.highlight').forEach(item => {
        item.classList.remove('highlight');
    });
    
    // 高亮当前文档
    const docElement = document.querySelector(`[data-node-id="${docId}"]`);
    if (docElement) {
        docElement.classList.add('highlight');
        
        // 展开父节点路径
        expandParentNodes(docElement.closest('.tree-node'));
        
        // 滚动到可见区域
        docElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // 3秒后移除高亮
        setTimeout(() => {
            docElement.classList.remove('highlight');
        }, 3000);
    }
}

// ============ 右键菜单预览功能 ============

function previewSelectedDocument() {
    if (selectedNode && selectedNode.type === 'file') {
        // 切换到搜索模式
        switchToSearchMode();
        // 预览文档
        previewDocument(selectedNode);
    }
    hideContextMenu();
}

// ============ 文件下载功能 ============

function downloadDocument(docId, fileName) {
    try {
        // 创建一个隐藏的链接来触发下载
        const downloadUrl = `/api/documents/${docId}/download`;
        
        // 创建临时的a标签用于下载
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = fileName;
        link.style.display = 'none';
        
        // 添加到页面并触发点击
        document.body.appendChild(link);
        link.click();
        
        // 清理
        document.body.removeChild(link);
        
        showSuccess('文件下载开始');
        
    } catch (error) {
        showError('下载失败: ' + error.message);
    }
}

// ============ Excel预览切换功能 ============

// 简化向量编辑功能，移除不必要的编辑模式切换
// 因为现在textarea默认就是可编辑状态，用户可以直接编辑然后点击"确定"保存

// 新增：向量编辑功能
let isVectorEditMode = false;
let editedChunks = {};

function toggleVectorEdit() {
    isVectorEditMode = !isVectorEditMode;
    const editBtn = document.getElementById('editVectorBtn');
    const vectorDiv = document.getElementById('vectorPanelContent');
    
    if (isVectorEditMode) {
        editBtn.innerHTML = '<i class="bi bi-check"></i> 保存';
        editBtn.className = 'btn btn-sm btn-success';
        
        // 添加编辑控制按钮
        const editControls = `
            <div class="vector-edit-controls">
                <button class="btn btn-outline-secondary" onclick="cancelVectorEdit()">
                    <i class="bi bi-x"></i> 取消
                </button>
                <button class="btn btn-primary" onclick="saveVectorEdit()">
                    <i class="bi bi-save"></i> 保存修改
                </button>
            </div>
        `;
        vectorDiv.insertAdjacentHTML('beforeend', editControls);
        
        // 使所有分段可编辑
        document.querySelectorAll('.vector-chunk-content').forEach((element, index) => {
            const originalContent = element.textContent;
            element.innerHTML = `<textarea class="form-control" style="min-height: 80px;" onchange="updateChunk(${index}, this.value)">${originalContent}</textarea>`;
        });
        
    } else {
        saveVectorEdit();
    }
}

function cancelVectorEdit() {
    isVectorEditMode = false;
    editedChunks = {};
    const editBtn = document.getElementById('editVectorBtn');
    editBtn.innerHTML = '<i class="bi bi-pencil"></i> 编辑';
    editBtn.className = 'btn btn-sm btn-outline-primary';
    
    // 重新加载向量信息
    if (selectedNode) {
        loadVectorizationInfo(selectedNode.id);
    }
}

// 保留updateChunk函数用于跟踪修改
function updateChunk(index, content) {
    editedChunks[index] = content;
}

function saveVectorEdit() {
    if (Object.keys(editedChunks).length === 0) {
        showInfo('没有需要保存的修改');
        return;
    }
    
    try {
        showInfo('正在保存修改...');
        
        // 这里可以添加保存到服务器的逻辑
        // const response = await fetch(`/api/vectorize/update/${selectedNode.id}`, {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify({ chunks: editedChunks })
        // });
        
        // 模拟保存成功
        setTimeout(() => {
            showSuccess('向量分段修改已保存');
            isVectorEditMode = false;
            editedChunks = {};
            
            const editBtn = document.getElementById('editVectorBtn');
            editBtn.innerHTML = '<i class="bi bi-pencil"></i> 编辑';
            editBtn.className = 'btn btn-sm btn-outline-primary';
            
            // 移除编辑控制按钮
            const editControls = document.querySelector('.vector-edit-controls');
            if (editControls) {
                editControls.remove();
            }
        }, 1000);
        
    } catch (error) {
        showError('保存失败: ' + error.message);
    }
}

// ============ 新增函数：显示节点及其所有父节点 ============

function showNodeAndParents(node) {
    let currentNode = node;
    while (currentNode && currentNode.classList.contains('tree-node')) {
        currentNode.style.display = 'block';
        
        // 展开父节点
        const expandBtn = currentNode.querySelector('.tree-expand-btn');
        const childrenContainer = currentNode.querySelector('.tree-children');
        
        if (expandBtn && childrenContainer && childrenContainer.classList.contains('collapsed')) {
            childrenContainer.classList.remove('collapsed');
            expandBtn.classList.add('expanded');
            const icon = expandBtn.querySelector('i');
            if (icon) {
                icon.className = 'bi bi-chevron-down';
            }
        }
        
        // 找到父级树节点
        currentNode = currentNode.parentElement?.closest('.tree-node');
    }
}

function showCreateFolderModal() {
    const modal = new bootstrap.Modal(document.getElementById('createFolderModal'));
    document.getElementById('folderName').value = '';
    document.getElementById('folderDescription').value = '';
    clearTagSelection('folder'); // 清空文件夹标签选择
    modal.show();
}

// ============ 新的向量化操作函数 ============

// 全局变量存储向量化数据
let currentVectorizationData = null;

async function rechunkTextInSidePanel() {
    const vectorizationPanel = document.getElementById('vectorizationPanel');
    const docId = vectorizationPanel.dataset.currentDocId;
    
    if (!docId) {
        showError('无效的文档ID');
        return;
    }
    
    try {
        const chunkSize = parseInt(document.getElementById('sideChunkSize').value) || 1000;
        const overlap = parseInt(document.getElementById('sideChunkOverlap').value) || 200;
        
        showInfo('正在重新分段，请稍候...');
        
        const response = await fetch(`/api/vectorize/preview/${docId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                chunk_size: chunkSize,
                overlap: overlap
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            displayVectorChunks(result.data.chunks);
            vectorizationPanel.dataset.vectorizationData = JSON.stringify(result.data);
            showSuccess('重新分段完成');
        } else {
            showError('重新分段失败: ' + result.error);
        }
    } catch (error) {
        showError('重新分段失败: ' + error.message);
    }
}

function resetVectorizationConfig() {
    document.getElementById('sideChunkSize').value = 1000;
    document.getElementById('sideChunkOverlap').value = 200;
    showInfo('配置已重置');
}

function cancelVectorization() {
    if (vectorizationMode) {
        closeVectorization();
        showInfo('已取消向量化操作');
    }
}

async function confirmVectorization() {
    const vectorizationPanel = document.getElementById('vectorizationPanel');
    const docId = vectorizationPanel.dataset.currentDocId;
    
    if (!docId) {
        showError('无效的文档ID');
        return;
    }
    
    try {
        // 收集编辑后的文本块
        const chunks = [];
        const textareas = vectorizationPanel.querySelectorAll('.chunk-textarea');
        
        textareas.forEach((textarea, index) => {
            const content = textarea.value.trim();
            if (content) {
                chunks.push({
                    id: `chunk_${index}`,
                    content: content
                });
            }
        });
        
        if (chunks.length === 0) {
            showWarning('没有可向量化的文本内容');
            return;
        }
        
        const confirmBtn = document.getElementById('confirmVectorization');
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 向量化中...';
        
        showInfo('正在执行向量化，请稍候...');
        
        const response = await fetch(`/api/vectorize/execute/${docId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ chunks })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess(`向量化完成！已处理 ${result.data.vectorized_chunks || chunks.length} 个文本块`);
            closeVectorization();
            
            // 更新当前预览文档的向量化状态
            updateVectorizationStatus(docId, true, result.data.vectorized_at);
            
            // 刷新文档详情
            if (selectedNode) {
                await showDocumentDetail(selectedNode);
            }
            loadStats();
        } else {
            showError('向量化失败: ' + result.error);
        }
    } catch (error) {
        showError('向量化失败: ' + error.message);
    } finally {
        const confirmBtn = document.getElementById('confirmVectorization');
        if (confirmBtn) {
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="bi bi-check"></i> 确认向量化';
        }
    }
}

function showSearchStrategyHint(strategy, query) {
    const hintElement = document.getElementById('searchStrategyHint');
    const strategyText = document.getElementById('strategyText');
    
    if (!hintElement || !strategyText) return;
    
    let hintText = '';
    if (strategy === 'hybrid') {
        hintText = '🧠 智能混合搜索：结合语义理解和关键词匹配';
        if (/[A-Z]{2,}/.test(query)) {
            hintText += '（检测到专业术语）';
        }
    } else {
        hintText = '🎯 语义搜索：基于文本语义理解';
    }
    
    strategyText.textContent = hintText;
    hintElement.style.display = 'block';
}

function hideSearchStrategyHint() {
    const hint = document.getElementById('searchStrategyHint');
    if (hint) {
        hint.style.display = 'none';
    }
}

// ============ 标签管理功能 ============

// 全局变量
let selectedUploadTags = [];
let selectedEditTags = [];
let selectedFolderTags = []; // 新增：文件夹标签选择
let availableTags = [];

// 初始化标签功能
async function initTagSystem() {
    try {
        await loadAvailableTags();
        initTagSelectors();
    } catch (error) {
        console.error('初始化标签系统失败:', error);
    }
}

// 加载可用标签
async function loadAvailableTags() {
    try {
        const response = await fetch('/api/tags/');
        const result = await response.json();
        
        if (result.success) {
            availableTags = result.data;
        } else {
            console.error('加载标签失败:', result.error);
        }
    } catch (error) {
        console.error('加载标签失败:', error);
    }
}

// 初始化标签选择器
function initTagSelectors() {
    // 上传标签选择器
    initTagSelector('uploadTagInput', 'uploadTagDropdown', 'uploadSelectedTags', selectedUploadTags);
    
    // 编辑标签选择器
    initTagSelector('editTagInput', 'editTagDropdown', 'editSelectedTags', selectedEditTags);
    
    // 文件夹标签选择器
    initTagSelector('folderTagInput', 'folderTagDropdown', 'folderSelectedTags', selectedFolderTags);
}

// 初始化单个标签选择器
function initTagSelector(inputId, dropdownId, selectedTagsId, selectedArray) {
    const input = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);
    const selectedTagsContainer = document.getElementById(selectedTagsId);
    
    if (!input || !dropdown || !selectedTagsContainer) {
        return;
    }
    
    // 输入事件
    input.addEventListener('input', function() {
        const query = this.value.trim();
        showTagDropdown(query, dropdown, selectedArray, inputId);
    });
    
    // 焦点事件
    input.addEventListener('focus', function() {
        const query = this.value.trim();
        showTagDropdown(query, dropdown, selectedArray, inputId);
    });
    
    // 失焦事件（延迟隐藏，允许点击下拉项）
    input.addEventListener('blur', function() {
        setTimeout(() => {
            dropdown.style.display = 'none';
        }, 200);
    });
    
    // 按键事件
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const query = this.value.trim();
            if (query) {
                createAndSelectTag(query, selectedArray, selectedTagsId, inputId);
                this.value = '';
                dropdown.style.display = 'none';
            }
        } else if (e.key === 'Escape') {
            dropdown.style.display = 'none';
        }
    });
}

// 显示标签下拉框
function showTagDropdown(query, dropdown, selectedArray, inputId) {
    const selectedIds = selectedArray.map(tag => tag.id);
    let filteredTags = availableTags.filter(tag => !selectedIds.includes(tag.id));
    
    if (query) {
        filteredTags = filteredTags.filter(tag => 
            tag.name.toLowerCase().includes(query.toLowerCase())
        );
    }
    
    let html = '';
    
    // 显示匹配的标签
    filteredTags.forEach(tag => {
        html += `
            <div class="tag-dropdown-item" onclick="selectTag(${tag.id}, '${tag.name}', '${tag.color}', '${inputId}')">
                <div class="tag-color-indicator" style="background-color: ${tag.color}"></div>
                <span>${tag.name}</span>
            </div>
        `;
    });
    
    // 如果有查询词且不存在完全匹配的标签，显示创建新标签选项
    if (query && !availableTags.some(tag => tag.name.toLowerCase() === query.toLowerCase())) {
        html += `
            <div class="tag-dropdown-item create-new" onclick="createAndSelectTag('${query}', getSelectedArrayByInput('${inputId}'), '${getSelectedTagsId(inputId)}', '${inputId}')">
                <i class="bi bi-plus-circle"></i>
                <span>创建标签 "${query}"</span>
            </div>
        `;
    }
    
    dropdown.innerHTML = html;
    dropdown.style.display = html ? 'block' : 'none';
}

// 选择标签
function selectTag(tagId, tagName, tagColor, inputId) {
    const selectedArray = getSelectedArrayByInput(inputId);
    const selectedTagsId = getSelectedTagsId(inputId);
    
    // 检查是否已选择
    if (selectedArray.some(tag => tag.id === tagId)) {
        return;
    }
    
    selectedArray.push({ id: tagId, name: tagName, color: tagColor });
    updateSelectedTagsDisplay(selectedTagsId, selectedArray);
    
    // 清空输入框并隐藏下拉框
    document.getElementById(inputId).value = '';
    document.getElementById(getDropdownId(inputId)).style.display = 'none';
}

// 创建并选择新标签
async function createAndSelectTag(tagName, selectedArray, selectedTagsId, inputId) {
    try {
        // 生成随机颜色
        const colors = ['#007bff', '#28a745', '#dc3545', '#ffc107', '#17a2b8', '#6f42c1', '#fd7e14', '#20c997'];
        const randomColor = colors[Math.floor(Math.random() * colors.length)];
        
        const response = await fetch('/api/tags/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: tagName,
                color: randomColor,
                description: `自动创建的标签`
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            const newTag = result.data;
            
            // 添加到可用标签列表
            availableTags.push(newTag);
            
            // 选择新创建的标签
            selectedArray.push({ id: newTag.id, name: newTag.name, color: newTag.color });
            updateSelectedTagsDisplay(selectedTagsId, selectedArray);
            
            showSuccess(`标签 "${tagName}" 创建成功`);
        } else {
            showError('创建标签失败: ' + result.error);
        }
    } catch (error) {
        console.error('创建标签失败:', error);
        showError('创建标签失败');
    }
}

// 移除标签
function removeTag(tagId, selectedArray, selectedTagsId) {
    const index = selectedArray.findIndex(tag => tag.id === tagId);
    if (index > -1) {
        selectedArray.splice(index, 1);
        updateSelectedTagsDisplay(selectedTagsId, selectedArray);
    }
}

// 更新已选择标签显示
function updateSelectedTagsDisplay(selectedTagsId, selectedArray) {
    const container = document.getElementById(selectedTagsId);
    if (!container) return;
    
    container.innerHTML = selectedArray.map(tag => `
        <span class="tag-badge" style="background-color: ${tag.color}">
            ${tag.name}
            <span class="remove-tag" onclick="removeTag(${tag.id}, getSelectedArrayByInput('${getInputIdBySelectedTags(selectedTagsId)}'), '${selectedTagsId}')">&times;</span>
        </span>
    `).join('');
}

// 根据输入框ID获取对应的选中标签数组
function getSelectedArrayByInput(inputId) {
    switch(inputId) {
        case 'uploadTagInput': return selectedUploadTags;
        case 'editTagInput': return selectedEditTags;
        case 'folderTagInput': return selectedFolderTags;
        default: return [];
    }
}

// 根据输入框ID获取对应的已选择标签容器ID
function getSelectedTagsId(inputId) {
    switch(inputId) {
        case 'uploadTagInput': return 'uploadSelectedTags';
        case 'editTagInput': return 'editSelectedTags';
        case 'folderTagInput': return 'folderSelectedTags';
        default: return '';
    }
}

// 根据输入框ID获取对应的下拉框ID
function getDropdownId(inputId) {
    switch(inputId) {
        case 'uploadTagInput': return 'uploadTagDropdown';
        case 'editTagInput': return 'editTagDropdown';
        case 'folderTagInput': return 'folderTagDropdown';
        default: return '';
    }
}

// 根据已选择标签容器ID获取对应的输入框ID
function getInputIdBySelectedTags(selectedTagsId) {
    switch(selectedTagsId) {
        case 'uploadSelectedTags': return 'uploadTagInput';
        case 'editSelectedTags': return 'editTagInput';
        case 'folderSelectedTags': return 'folderTagInput';
        default: return '';
    }
}

// 清空标签选择
function clearTagSelection(type) {
    if (type === 'upload') {
        selectedUploadTags.length = 0;
        updateSelectedTagsDisplay('uploadSelectedTags', selectedUploadTags);
        document.getElementById('uploadTagInput').value = '';
    } else if (type === 'edit') {
        selectedEditTags.length = 0;
        updateSelectedTagsDisplay('editSelectedTags', selectedEditTags);
        document.getElementById('editTagInput').value = '';
    } else if (type === 'folder') {
        selectedFolderTags.length = 0;
        updateSelectedTagsDisplay('folderSelectedTags', selectedFolderTags);
        const folderTagInput = document.getElementById('folderTagInput');
        if (folderTagInput) {
            folderTagInput.value = '';
        }
    }
}

// 设置编辑标签
function setEditTags(tags) {
    selectedEditTags.length = 0;
    if (tags && Array.isArray(tags)) {
        selectedEditTags.push(...tags);
        updateSelectedTagsDisplay('editSelectedTags', selectedEditTags);
    }
}

// 获取标签ID数组
function getTagIds(selectedArray) {
    return selectedArray.map(tag => tag.id);
}

// 在文档树节点中显示标签
function renderNodeTags(tags) {
    if (!tags || tags.length === 0) {
        return '';
    }
    
    return `<span class="node-tags">${tags.map(tag => 
        `<span class="node-tag" style="background-color: ${tag.color}">${tag.name}</span>`
    ).join('')}</span>`;
}

// 页面加载时初始化标签系统
document.addEventListener('DOMContentLoaded', function() {
    initTagSystem();
});

// 添加一个函数来实时更新向量化状态显示
function updateVectorizationStatus(docId, isVectorized, vectorizedAt) {
    // 更新全局文档对象
    if (currentPreviewDocument && currentPreviewDocument.id == docId) {
        currentPreviewDocument.is_vectorized = isVectorized;
        currentPreviewDocument.vectorized_at = vectorizedAt;
        
        // 重新生成文档信息显示
        const infoElements = document.querySelectorAll('.document-info-horizontal');
        infoElements.forEach(element => {
            if (element.querySelector('.bi-file-earmark')) {
                element.outerHTML = generateDocumentInfo(currentPreviewDocument);
            }
        });
        
        // 更新向量化按钮
        const vectorizeBtn = document.getElementById('vectorizeBtn');
        if (vectorizeBtn) {
            if (isVectorized) {
                vectorizeBtn.innerHTML = `
                    <i class="bi bi-vector-pen"></i>
                    查看向量化
                `;
            } else {
                vectorizeBtn.innerHTML = `
                    <i class="bi bi-vector-pen"></i>
                    向量化
                `;
            }
        }
    }
}

// ============ LLM模型管理功能 ============

async function initLLMModelSelector() {
    // 初始化LLM模型选择器
    try {
        await loadLLMModels();
        setupLLMModelChangeHandler();
    } catch (error) {
        console.error('初始化LLM模型选择器失败:', error);
        showError('加载LLM模型配置失败: ' + error.message);
    }
}

async function loadLLMModels() {
    // 从后端加载可用的LLM模型
    try {
        const response = await fetch('/api/config/llm-models');
        const result = await response.json();
        
        if (result.success) {
            availableLLMModels = result.data.models;
            llmFeatures = result.data.features;
            selectedLLMModel = result.data.default;
            
            updateLLMModelSelector();
            updateLLMFeatureStatus();
        } else {
            throw new Error(result.error || '获取LLM模型配置失败');
        }
    } catch (error) {
        console.error('加载LLM模型失败:', error);
        
        // 设置默认选项
        const llmSelect = document.getElementById('llmModelSelect');
        if (llmSelect) {
            llmSelect.innerHTML = '<option value="">LLM服务不可用</option>';
            llmSelect.disabled = true;
        }
        
        throw error;
    }
}

function updateLLMModelSelector() {
    // 更新LLM模型选择器的选项
    const llmSelect = document.getElementById('llmModelSelect');
    if (!llmSelect) return;
    
    // 清空现有选项
    llmSelect.innerHTML = '';
    
    if (availableLLMModels.length === 0) {
        llmSelect.innerHTML = '<option value="">暂无可用模型</option>';
        llmSelect.disabled = true;
        return;
    }
    
    // 按provider分组显示
    const groupedModels = {};
    availableLLMModels.forEach(model => {
        if (!groupedModels[model.provider_name]) {
            groupedModels[model.provider_name] = [];
        }
        groupedModels[model.provider_name].push(model);
    });
    
    // 添加选项
    Object.entries(groupedModels).forEach(([providerName, models]) => {
        const optgroup = document.createElement('optgroup');
        optgroup.label = providerName;
        
        models.forEach(model => {
            const option = document.createElement('option');
            option.value = model.full_key;
            option.textContent = model.model_name;
            option.disabled = !model.is_available;
            
            if (!model.is_available) {
                option.textContent += ' (不可用)';
            }
            
            optgroup.appendChild(option);
        });
        
        llmSelect.appendChild(optgroup);
    });
    
    // 设置默认选择
    if (selectedLLMModel) {
        llmSelect.value = selectedLLMModel;
    }
    
    llmSelect.disabled = false;
}

function setupLLMModelChangeHandler() {
    // 设置LLM模型选择变化处理器
    const llmSelect = document.getElementById('llmModelSelect');
    if (!llmSelect) return;
    
    llmSelect.addEventListener('change', function(e) {
        selectedLLMModel = e.target.value;
        console.log('选择的LLM模型:', selectedLLMModel);
        
        // 可以在这里添加模型切换的后续处理
        if (selectedLLMModel) {
            showInfo(`已选择模型: ${getSelectedModelDisplayName()}`);
        }
    });
}

function getSelectedModelDisplayName() {
    // 获取当前选中模型的显示名称
    if (!selectedLLMModel) return '未选择';
    
    const model = availableLLMModels.find(m => m.full_key === selectedLLMModel);
    return model ? model.display_name : selectedLLMModel;
}

function updateLLMFeatureStatus() {
    // 更新LLM功能状态显示
    console.log('LLM功能状态:', llmFeatures);
    
    // 可以在这里添加UI更新逻辑，比如显示哪些功能已启用
    if (llmFeatures.query_optimization) {
        console.log('✅ 查询优化功能已启用');
    }
    if (llmFeatures.result_reranking) {
        console.log('✅ 结果重排序功能已启用');
    }
    if (llmFeatures.answer_generation) {
        console.log('✅ 答案生成功能已启用');
    }
}

function isLLMAvailable() {
    // 检查是否有可用的LLM模型
    return selectedLLMModel && availableLLMModels.some(m => m.full_key === selectedLLMModel && m.is_available);
}

function getLLMConfig() {
    // 获取当前LLM配置信息
    return {
        model: selectedLLMModel,
        features: llmFeatures,
        isAvailable: isLLMAvailable()
    };
}

// 从聊天中选择文件的处理函数
async function selectFileFromChat(docId) {
    try {
        console.log(`开始选择文件，文档ID: ${docId}`);
        
        // 1. 首先尝试从当前nodeMap中查找
        let node = findNodeById(docId);
        console.log(`在nodeMap中查找结果:`, node ? `找到文档 ${node.name}` : '未找到');
        
        if (!node) {
            // 2. 如果nodeMap中没有，从API获取文档详情
            console.log(`文档 ${docId} 不在当前nodeMap中，从API获取详情...`);
            
            try {
                const response = await fetch(`/api/documents/${docId}/detail`);
                const result = await response.json();
                console.log('API响应:', result);
                
                if (result.success) {
                    node = result.data;
                    console.log(`通过API获取到文档: ${node.name}`);
                } else {
                    console.error('API返回失败:', result);
                    showToast('无法获取文档信息', 'warning');
                    return;
                }
            } catch (apiError) {
                console.error('API获取文档详情失败:', apiError);
                showToast('获取文档信息时出现错误', 'error');
                return;
            }
        }
        
        console.log('准备执行文档定位和预览操作...');
        
        // 3. 在文档树中高亮显示该文件
        try {
            highlightDocumentInTree(docId);
            console.log('文档树高亮完成');
        } catch (error) {
            console.warn('文档树高亮失败:', error);
        }
        
        // 4. 展开父节点以确保文件可见（如果在树中）
        const nodeElement = document.querySelector(`[data-node-id="${docId}"]`);
        console.log(`DOM中查找节点元素:`, nodeElement ? '找到' : '未找到');
        if (nodeElement) {
            try {
                expandParentNodes(nodeElement);
                console.log('父节点展开完成');
            } catch (error) {
                console.warn('展开父节点失败:', error);
            }
        }
        
        // 5. 预览文件内容
        try {
            console.log('开始预览文档...');
            await previewDocument(node);
            console.log('文档预览完成');
        } catch (error) {
            console.error('预览文档失败:', error);
            showToast('预览文档时出现错误', 'warning');
        }
        
        // 6. 设置为选中状态
        try {
            selectedNode = node;
            if (nodeElement) {
                clearTreeSelection();
                nodeElement.classList.add('selected');
                console.log('节点选中状态设置完成');
            }
        } catch (error) {
            console.warn('设置选中状态失败:', error);
        }
        
        // 7. 显示成功提示
        showToast(`已定位到文档：${node.name}`, 'success', 2000);
        console.log(`文件选择完成: ${node.name}`);
        
    } catch (error) {
        console.error('选择文件失败:', error);
        showToast('定位文档时出现错误', 'error');
    }
}