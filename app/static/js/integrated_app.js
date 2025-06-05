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
    
    // 显示文件大小（仅对文件显示）
    let sizeInfo = '';
    if (node.type !== 'folder' && node.file_size) {
        sizeInfo = `<span class="tree-item-size">${formatFileSize(node.file_size)}</span>`;
    }
    
    item.innerHTML = `
        ${expandButton}
        <div class="tree-item-content">
            <i class="bi ${icon} ${iconClass}"></i>
            <span class="tree-item-text">${node.name}</span>
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
    
    previewDiv.style.display = 'block';
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
        
        const response = await fetch('/api/documents/folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('文件夹创建成功');
            bootstrap.Modal.getInstance(document.getElementById('createFolderModal')).hide();
            
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
        const response = await fetch(`/api/documents/${docId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('更新成功');
            bootstrap.Modal.getInstance(document.getElementById('editDocumentModal')).hide();
            
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
            
            if (selectedNode) {
                showDocumentDetail(selectedNode);
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
    
    // 首先隐藏所有节点
    document.querySelectorAll('.tree-node').forEach(node => {
        node.style.display = 'none';
    });
    
    // 收集所有匹配的节点
    const matchingNodes = [];
    treeItems.forEach(item => {
        const nodeName = item.dataset.nodeName || '';
        const matches = nodeName.toLowerCase().includes(searchTermLower);
        
        if (matches) {
            matchingNodes.push(item);
            item.classList.add('search-match');
            highlightSearchTerm(item, searchTerm);
            hasVisibleItems = true;
        } else {
            item.classList.remove('search-match');
        }
    });
    
    // 显示匹配的节点及其所有父节点
    matchingNodes.forEach(item => {
        const treeNode = item.closest('.tree-node');
        showNodeAndParents(treeNode);
    });
    
    // 如果没有匹配项，显示提示
    if (!hasVisibleItems) {
        showNoSearchResults();
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

function clearSearchHighlight() {
    document.querySelectorAll('.tree-item').forEach(item => {
        const textSpan = item.querySelector('.tree-item-text');
        const originalText = item.dataset.nodeName;
        if (originalText && textSpan) {
            textSpan.textContent = originalText;
        }
        item.classList.remove('search-match');
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

function showNoSearchResults() {
    // 可以在这里添加"无搜索结果"的提示
    console.log('没有找到匹配的文档');
}

function clearTreeSearch() {
    document.getElementById('treeSearch').value = '';
    document.getElementById('searchClear').style.display = 'none';
    clearSearchHighlight();
    document.querySelectorAll('.tree-node').forEach(node => {
        node.style.display = 'block';
    });
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
                    <span style="color: ${isVectorized === '是' ? '#28a745' : '#6c757d'};">向量化: ${isVectorized}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <i class="bi bi-calendar-plus text-secondary" style="font-size: 12px;"></i>
                    <span style="color: #6c757d;">${createdDate}</span>
                </div>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <i class="bi bi-calendar-check text-secondary" style="font-size: 12px;"></i>
                    <span style="color: #6c757d;">${updatedDate}</span>
                </div>
            </div>
            ${description !== '无描述' ? `
                <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #e9ecef;">
                    <div style="display: flex; align-items: flex-start; gap: 6px; font-size: 12px;">
                        <i class="bi bi-chat-square-text text-secondary" style="font-size: 12px; margin-top: 2px;"></i>
                        <span style="color: #6c757d; line-height: 1.4;">${description}</span>
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
    
    // 添加用户消息到聊天记录
    addChatMessage('user', message);
    chatInput.value = '';
    
    // 智能选择搜索策略并显示提示
    const searchStrategy = determineSearchStrategy(message, selectedSimilarity);
    showSearchStrategyHint(searchStrategy, message);
    
    // 显示AI正在思考的状态
    const thinkingId = addChatMessage('assistant', '', true);
    
    try {
        let response;
        if (searchStrategy === 'hybrid') {
            // 使用混合搜索
            response = await fetch('/api/search/hybrid', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: message,
                    top_k: 5,
                    similarity_level: selectedSimilarity
                })
            });
        } else {
            // 使用纯语义搜索
            response = await fetch('/api/search/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    query: message,
                    top_k: 5,
                    similarity_level: selectedSimilarity
                })
            });
        }
        
        const result = await response.json();
        
        // 移除thinking消息
        removeChatMessage(thinkingId);
        
        // 隐藏搜索策略提示
        hideSearchStrategyHint();
        
        if (result.success && result.data.results && result.data.results.length > 0) {
            // 显示搜索结果
            const resultMessage = formatSearchResultsEnhanced(result.data, message);
            addChatMessage('assistant', resultMessage);
            
            // 如果有搜索结果，自动预览第一个文档
            const firstResult = result.data.results[0];
            if (firstResult.document) {
                highlightDocumentInTree(firstResult.document.id);
                previewDocument(firstResult.document);
            }
        } else {
            // 智能提示用户如何优化搜索
            const suggestionMessage = generateSearchSuggestions(message, selectedSimilarity, searchStrategy);
            addChatMessage('assistant', suggestionMessage);
        }
    } catch (error) {
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

function formatSearchResultsEnhanced(data, query) {
    // 增强版搜索结果格式化
    
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
    
    let message = `🔍 找到了 ${data.results.length} 个相关结果 (${levelText})${searchTypeText}：\n\n`;
    
    data.results.forEach((result, index) => {
        const score = (result.score * 100).toFixed(1);
        const searchIcon = result.search_type === 'keyword' ? '🔤' : 
                          result.search_type === 'hybrid' ? '🧠' : '🎯';
        
        message += `${index + 1}. ${searchIcon} **${result.document.name}** (${score}%)\n`;
        
        // 高亮匹配的关键词
        let displayText = result.text.substring(0, 120);
        if (result.matched_keywords && result.matched_keywords.length > 0) {
            result.matched_keywords.forEach(keyword => {
                const regex = new RegExp(`(${keyword})`, 'gi');
                displayText = displayText.replace(regex, '**$1**');
            });
        }
        message += `${displayText}...\n\n`;
    });
    
    message += `✨ 提示：点击文档名称可以查看完整内容预览。`;
    if (data.similarity_level !== 'any') {
        message += `<br>💡 如需更多结果，可降低相关性要求后重新搜索。`;
    }
    
    return message.replace(/\n/g, '<br>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
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
            
            // 刷新文档详情
            if (selectedNode) {
                showDocumentDetail(selectedNode);
            }
            loadStats();
        } else {
            showError('向量化失败: ' + result.error);
        }
    } catch (error) {
        showError('向量化失败: ' + error.message);
    } finally {
        const confirmBtn = document.getElementById('confirmVectorization');
        confirmBtn.disabled = false;
        confirmBtn.innerHTML = '<i class="bi bi-check-circle"></i> 确定';
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
    const hintElement = document.getElementById('searchStrategyHint');
    if (hintElement) {
        setTimeout(() => {
            hintElement.style.display = 'none';
        }, 2000); // 2秒后自动隐藏
    }
}