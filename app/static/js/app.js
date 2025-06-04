// 全局变量
let currentParentId = null;
let selectedNode = null;
let selectedFiles = []; // 存储选择的文件（用于文件夹上传）

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    loadFileTree();
    loadStats();
    initUploadArea();
    
    // 绑定回车键搜索
    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch();
        }
    });
    
    // 添加调试功能到全局作用域
    window.debugCurrentState = debugCurrentState;
    window.resetSelectionManually = resetSelection;
});

// 加载文档树
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

// 渲染文档树
function renderFileTree(nodes) {
    const treeContainer = document.getElementById('fileTree');
    
    // 清除现有内容
    treeContainer.innerHTML = '';
    
    if (!nodes || nodes.length === 0) {
        treeContainer.innerHTML = `
            <div class="text-center text-muted py-4">
                <i class="bi bi-folder2-open" style="font-size: 2rem;"></i>
                <p class="mt-2">暂无文档</p>
                <small>可以点击"上传文件"或"新建文件夹"开始</small>
            </div>
        `;
        return;
    }
    
    // 渲染节点
    nodes.forEach(node => {
        const nodeElement = createTreeNode(node, 0);
        treeContainer.appendChild(nodeElement);
    });
    
    // 渲染完成后的状态检查
    console.log(`文档树渲染完成，共 ${nodes.length} 个顶级节点`);
}

// 创建树节点
function createTreeNode(node, level) {
    const div = document.createElement('div');
    div.style.marginLeft = (level * 20) + 'px';
    
    const item = document.createElement('div');
    item.className = 'tree-item';
    item.dataset.nodeId = node.id;
    item.dataset.nodeType = node.type;
    
    const icon = node.type === 'folder' ? 'bi-folder' : getFileIcon(node.file_type);
    const name = node.name || '未命名';
    
    item.innerHTML = `
        <i class="bi ${icon}"></i>
        <span class="ms-2">${name}</span>
        ${node.type === 'file' ? `<small class="text-muted ms-2">(${formatFileSize(node.file_size)})</small>` : ''}
    `;
    
    item.addEventListener('click', function(e) {
        e.stopPropagation();
        selectNode(node);
    });
    
    // 为文件夹添加右键菜单
    if (node.type === 'folder') {
        item.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            showFolderContextMenu(e, node);
        });
    }
    
    div.appendChild(item);
    
    // 递归添加子节点
    if (node.children && node.children.length > 0) {
        node.children.forEach(child => {
            const childElement = createTreeNode(child, level + 1);
            div.appendChild(childElement);
        });
    }
    
    return div;
}

// 选择节点
function selectNode(node) {
    // 移除之前的选中状态
    document.querySelectorAll('.tree-item.selected').forEach(item => {
        item.classList.remove('selected');
    });
    
    // 选中当前节点
    const nodeElement = document.querySelector(`[data-node-id="${node.id}"]`);
    if (nodeElement) {
        nodeElement.classList.add('selected');
    }
    
    selectedNode = node;
    currentParentId = node.type === 'folder' ? node.id : node.parent_id;
    
    // 更新当前路径显示
    updateCurrentPath(node);
    
    // 显示文档详情（文件和文件夹都显示）
    showDocumentDetail(node);
}

// 更新当前路径显示
function updateCurrentPath(node) {
    const pathDiv = document.getElementById('currentPath');
    
    if (!node) {
        pathDiv.innerHTML = '<i class="bi bi-house"></i> 根目录';
        return;
    }
    
    if (node.type === 'folder') {
        pathDiv.innerHTML = `<i class="bi bi-folder"></i> ${node.name}`;
    } else {
        // 对于文件，显示其父文件夹路径
        if (node.parent_id) {
            pathDiv.innerHTML = `<i class="bi bi-folder"></i> 在 "${selectedNode.parent_name || '文件夹'}" 中`;
        } else {
            pathDiv.innerHTML = '<i class="bi bi-house"></i> 根目录';
        }
    }
}

// 显示文档详情
async function showDocumentDetail(node) {
    try {
        const response = await fetch(`/api/documents/${node.id}/detail`);
        const result = await response.json();
        
        if (result.success) {
            const detailDiv = document.getElementById('documentDetail');
            const infoDiv = document.getElementById('documentInfo');
            
            const doc = result.data;
            
            let actionButtons = '';
            if (doc.type === 'file') {
                // 根据文件类型和向量化状态调整按钮
                const isPDF = doc.file_type === 'pdf' || (doc.file_path && doc.file_path.toLowerCase().endsWith('.pdf'));
                const isVectorized = doc.is_vectorized;
                
                actionButtons = `
                    <div class="btn-group" role="group">
                        <button class="btn btn-sm btn-outline-primary" onclick="processDocument(${doc.id})">
                            <i class="bi bi-gear"></i> 处理文档
                        </button>
                        ${isPDF ? `
                            <button class="btn btn-sm ${isVectorized ? 'btn-outline-info' : 'btn-outline-success'}" onclick="vectorizeDocument(${doc.id})">
                                <i class="bi bi-vector-pen"></i> ${isVectorized ? '重新向量化' : '向量化'}
                            </button>
                        ` : ''}
                        <button class="btn btn-sm btn-outline-warning" onclick="showEditDocumentModal(${doc.id}, '${doc.name}', '${doc.description || ''}', 'file')">
                            <i class="bi bi-pencil"></i> 编辑
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteDocument(${doc.id})">
                            <i class="bi bi-trash"></i> 删除
                        </button>
                    </div>
                `;
            } else {
                // 文件夹
                actionButtons = `
                    <div class="btn-group" role="group">
                        <button class="btn btn-sm btn-outline-warning" onclick="showEditDocumentModal(${doc.id}, '${doc.name}', '${doc.description || ''}', 'folder')">
                            <i class="bi bi-pencil"></i> 编辑
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="deleteDocument(${doc.id})">
                            <i class="bi bi-trash"></i> 删除
                        </button>
                    </div>
                `;
            }
            
            // 构建向量化状态信息
            let vectorizationInfo = '';
            if (doc.type === 'file' && doc.is_vectorized) {
                const metadata = doc.metadata || {};
                const vectorData = metadata.vectorization || {};
                
                vectorizationInfo = `
                    <div class="mt-3">
                        <h6><i class="bi bi-vector-pen text-success me-2"></i>向量化信息</h6>
                        <div class="card bg-light">
                            <div class="card-body py-2">
                                <div class="row">
                                    <div class="col-md-4">
                                        <small class="text-muted">状态:</small>
                                        <span class="badge bg-success ms-1">${doc.vector_status || 'completed'}</span>
                                    </div>
                                    <div class="col-md-4">
                                        <small class="text-muted">文本块:</small>
                                        <strong class="ms-1">${vectorData.chunk_count || 0}</strong>
                                    </div>
                                    <div class="col-md-4">
                                        <small class="text-muted">完成时间:</small>
                                        <small class="ms-1">${doc.vectorized_at ? formatDateTime(doc.vectorized_at) : '未知'}</small>
                                    </div>
                                </div>
                                ${vectorData.minio_path ? `
                                    <div class="row mt-2">
                                        <div class="col-12">
                                            <small class="text-muted">存储路径:</small>
                                            <code class="ms-1">${vectorData.minio_path}</code>
                                        </div>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `;
            }
            
            infoDiv.innerHTML = `
                <div class="card">
                    <div class="card-body">
                        <h6 class="card-title">
                            <i class="bi ${doc.type === 'folder' ? 'bi-folder' : getFileIcon(doc.file_type)}"></i>
                            ${doc.name}
                        </h6>
                        <p class="card-text">
                            <strong>类型:</strong> ${doc.type === 'folder' ? '文件夹' : doc.file_type}<br>
                            ${doc.type === 'file' ? `<strong>大小:</strong> ${formatFileSize(doc.file_size)}<br>` : ''}
                            <strong>创建时间:</strong> ${formatDateTime(doc.created_at)}<br>
                            <strong>描述:</strong> ${doc.description || '无'}
                        </p>
                        ${actionButtons}
                        ${vectorizationInfo}
                        ${doc.content_info ? `
                            <div class="mt-3">
                                <h6>内容信息</h6>
                                <p class="small text-muted">
                                    内容块数: ${doc.content_info.total_contents}<br>
                                    文本块数: ${doc.content_info.total_chunks}<br>
                                    向量状态: ${doc.content_info.vector_status.join(', ')}
                                </p>
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
            
            detailDiv.style.display = 'block';
            document.getElementById('searchResults').style.display = 'none';
        } else {
            showError('获取文档详情失败: ' + result.error);
        }
    } catch (error) {
        showError('获取文档详情失败: ' + error.message);
    }
}

// 执行搜索
async function performSearch() {
    const query = document.getElementById('searchInput').value.trim();
    const searchType = document.getElementById('searchType').value;
    
    if (!query) {
        showError('请输入搜索内容');
        return;
    }
    
    try {
        let url, body;
        
        if (searchType === 'semantic') {
            url = '/api/search/';
            body = JSON.stringify({
                query: query,
                top_k: 10
            });
        } else {
            url = `/api/search/documents?q=${encodeURIComponent(query)}`;
        }
        
        const options = {
            method: searchType === 'semantic' ? 'POST' : 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (searchType === 'semantic') {
            options.body = body;
        }
        
        const response = await fetch(url, options);
        const result = await response.json();
        
        if (result.success) {
            displaySearchResults(result.data, searchType);
        } else {
            showError('搜索失败: ' + result.error);
        }
    } catch (error) {
        showError('搜索失败: ' + error.message);
    }
}

// 显示搜索结果
function displaySearchResults(data, searchType) {
    const resultsDiv = document.getElementById('searchResults');
    const listDiv = document.getElementById('resultsList');
    
    if (!data.results || data.results.length === 0) {
        listDiv.innerHTML = '<p class="text-muted">没有找到相关结果</p>';
    } else {
        listDiv.innerHTML = '';
        
        data.results.forEach(result => {
            const item = document.createElement('div');
            item.className = 'result-item';
            
            if (searchType === 'semantic') {
                item.innerHTML = `
                    <div class="d-flex justify-content-between align-items-start">
                        <div>
                            <h6 class="mb-1">${result.document.name}</h6>
                            <p class="mb-1">${result.text}</p>
                            <small class="text-muted">
                                文档类型: ${result.document.file_type} | 
                                页码: ${result.chunk_index || 'N/A'}
                            </small>
                        </div>
                        <span class="badge bg-primary score-badge">
                            ${(result.score * 100).toFixed(1)}%
                        </span>
                    </div>
                `;
            } else {
                item.innerHTML = `
                    <div>
                        <h6 class="mb-1">${result.name}</h6>
                        <p class="mb-1">${result.description || '无描述'}</p>
                        <small class="text-muted">
                            类型: ${result.file_type || result.type} | 
                            大小: ${formatFileSize(result.file_size)} |
                            创建时间: ${formatDateTime(result.created_at)}
                        </small>
                    </div>
                `;
            }
            
            item.addEventListener('click', function() {
                const docId = searchType === 'semantic' ? result.document.id : result.id;
                selectNodeById(docId);
            });
            
            listDiv.appendChild(item);
        });
    }
    
    resultsDiv.style.display = 'block';
    document.getElementById('documentDetail').style.display = 'none';
}

// 根据ID选择节点
function selectNodeById(nodeId) {
    selectedNode = { id: nodeId };
    fetch(`/api/documents/${nodeId}/detail`)
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                showDocumentDetail(result.data);
            }
        });
}

// 显示创建文件夹模态框
function showCreateFolderModal() {
    const modal = new bootstrap.Modal(document.getElementById('createFolderModal'));
    document.getElementById('folderName').value = '';
    document.getElementById('folderDescription').value = '';
    
    // 重置为普通文件夹创建模式
    const title = document.querySelector('#createFolderModal .modal-title');
    title.textContent = '创建文件夹';
    
    modal.show();
}

// 创建文件夹
async function createFolder() {
    const name = document.getElementById('folderName').value.trim();
    const description = document.getElementById('folderDescription').value.trim();
    
    if (!name) {
        showError('请输入文件夹名称');
        return;
    }
    
    try {
        const requestData = {
            name: name,
            description: description
        };
        
        // 只有当currentParentId不为null时才添加parent_id
        if (currentParentId !== null) {
            requestData.parent_id = currentParentId;
        }
        
        const response = await fetch('/api/documents/folder', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            const folderType = currentParentId === null ? '顶级文件夹' : '文件夹';
            showSuccess(`${folderType}创建成功`);
            bootstrap.Modal.getInstance(document.getElementById('createFolderModal')).hide();
            loadFileTree();
            
            // 如果是创建顶级文件夹，重置选择状态
            if (currentParentId === null) {
                resetSelection();
            }
        } else {
            showError('创建文件夹失败: ' + result.error);
        }
    } catch (error) {
        showError('创建文件夹失败: ' + error.message);
    }
}

// 显示上传文件模态框
function showUploadModal() {
    const modal = new bootstrap.Modal(document.getElementById('uploadModal'));
    document.getElementById('fileDescription').value = '';
    document.getElementById('uploadProgress').style.display = 'none';
    
    // 彻底清理上传状态
    clearFolderUploadState();
    
    // 确保上传区域显示正确
    updateUploadAreaDisplay();
    
    modal.show();
}

// 初始化上传区域
function initUploadArea() {
    const uploadArea = document.getElementById('uploadArea');
    const fileInput = document.getElementById('fileInput');
    const folderInput = document.getElementById('folderInput');
    
    // 移除可能存在的旧事件监听器（通过克隆元素的方式）
    function removeAllEventListeners(element) {
        const newElement = element.cloneNode(true);
        element.parentNode.replaceChild(newElement, element);
        return newElement;
    }
    
    // 监听上传类型切换
    document.querySelectorAll('input[name="uploadType"]').forEach(radio => {
        radio.removeEventListener('change', handleUploadTypeChange);
        radio.addEventListener('change', handleUploadTypeChange);
    });
    
    // 上传区域点击事件 - 使用事件委托避免重复绑定
    uploadArea.removeEventListener('click', handleUploadAreaClick);
    uploadArea.addEventListener('click', handleUploadAreaClick);
    
    // 文件选择变化监听
    fileInput.removeEventListener('change', handleFileInputChange);
    fileInput.addEventListener('change', handleFileInputChange);
    
    // 文件夹选择变化监听
    folderInput.removeEventListener('change', handleFolderInputChange);
    folderInput.addEventListener('change', handleFolderInputChange);
    
    // 拖拽事件
    uploadArea.removeEventListener('dragover', handleDragOver);
    uploadArea.removeEventListener('dragleave', handleDragLeave);
    uploadArea.removeEventListener('drop', handleDrop);
    
    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
}

// 事件处理函数
function handleUploadTypeChange() {
    updateUploadAreaDisplay();
    hideFileListPreview();
}

function handleUploadAreaClick() {
    const uploadType = document.querySelector('input[name="uploadType"]:checked').value;
    if (uploadType === 'folder') {
        document.getElementById('folderInput').click();
    } else {
        document.getElementById('fileInput').click();
    }
}

function handleFileInputChange(e) {
    selectedFiles = Array.from(e.target.files);
    updateUploadAreaDisplay();
    hideFileListPreview();
}

function handleFolderInputChange(e) {
    selectedFiles = Array.from(e.target.files);
    updateUploadAreaDisplay();
    showFileListPreview();
}

function handleDragOver(e) {
    e.preventDefault();
    document.getElementById('uploadArea').classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    document.getElementById('uploadArea').classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    document.getElementById('uploadArea').classList.remove('dragover');
    
    const items = e.dataTransfer.items;
    if (items) {
        handleDroppedItems(items);
    }
}

// 处理拖拽的文件/文件夹
async function handleDroppedItems(items) {
    selectedFiles = [];
    
    for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === 'file') {
            const entry = item.webkitGetAsEntry();
            if (entry) {
                if (entry.isDirectory) {
                    // 处理文件夹
                    document.getElementById('uploadTypeFolder').checked = true;
                    await traverseDirectory(entry, '');
                } else {
                    // 处理文件
                    const file = item.getAsFile();
                    if (file) {
                        selectedFiles.push(file);
                    }
                }
            }
        }
    }
    
    updateUploadAreaDisplay();
    if (selectedFiles.length > 1 || document.getElementById('uploadTypeFolder').checked) {
        showFileListPreview();
    } else {
        hideFileListPreview();
    }
}

// 遍历目录获取所有文件
function traverseDirectory(dirEntry, path) {
    return new Promise((resolve) => {
        const dirReader = dirEntry.createReader();
        
        function readEntries() {
            dirReader.readEntries(async (entries) => {
                if (entries.length === 0) {
                    resolve();
                    return;
                }
                
                for (const entry of entries) {
                    const entryPath = path ? `${path}/${entry.name}` : entry.name;
                    
                    if (entry.isFile) {
                        await new Promise((fileResolve) => {
                            entry.file((file) => {
                                // 创建文件对象并添加路径信息
                                Object.defineProperty(file, 'webkitRelativePath', {
                                    value: entryPath,
                                    writable: false
                                });
                                selectedFiles.push(file);
                                fileResolve();
                            });
                        });
                    } else if (entry.isDirectory) {
                        await traverseDirectory(entry, entryPath);
                    }
                }
                
                readEntries(); // 继续读取下一批
            });
        }
        
        readEntries();
    });
}

// 更新上传区域显示
function updateUploadAreaDisplay() {
    const uploadArea = document.getElementById('uploadArea');
    const uploadType = document.querySelector('input[name="uploadType"]:checked').value;
    
    if (selectedFiles.length > 0) {
        const isFolder = uploadType === 'folder' || selectedFiles.length > 1;
        const totalSize = selectedFiles.reduce((sum, file) => sum + file.size, 0);
        
        if (isFolder) {
            uploadArea.innerHTML = `
                <i class="bi bi-folder-check" style="font-size: 3rem; color: #28a745;"></i>
                <h5 class="mt-3 text-success">已选择文件夹</h5>
                <p class="mb-2"><strong>${selectedFiles.length}</strong> 个文件</p>
                <p class="text-muted">总大小: ${formatFileSize(totalSize)}</p>
                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="clearSelectedFiles()">
                    <i class="bi bi-x-circle"></i> 重新选择
                </button>
            `;
        } else {
            const file = selectedFiles[0];
            uploadArea.innerHTML = `
                <i class="bi bi-file-check" style="font-size: 3rem; color: #28a745;"></i>
                <h5 class="mt-3 text-success">已选择文件</h5>
                <p class="mb-2"><strong>${file.name}</strong></p>
                <p class="text-muted">大小: ${formatFileSize(file.size)}</p>
                <button type="button" class="btn btn-sm btn-outline-secondary" onclick="clearSelectedFiles()">
                    <i class="bi bi-x-circle"></i> 重新选择
                </button>
            `;
        }
    } else {
        // 恢复默认显示
        const isFolder = uploadType === 'folder';
        uploadArea.innerHTML = `
            <i class="bi bi-cloud-upload" style="font-size: 3rem; color: #6c757d;"></i>
            <h5 class="mt-3">${isFolder ? '拖拽文件夹到此处或点击选择文件夹' : '拖拽文件到此处或点击选择文件'}</h5>
            <p class="text-muted">${isFolder ? '支持整个文件夹上传，保持目录结构' : '支持 PDF, Word, Excel, 图片, 视频文件'}</p>
            <input type="file" id="fileInput" style="display: none;" 
                   accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif,.bmp,.mp4,.avi,.mov,.wmv,.flv,.mkv">
            <input type="file" id="folderInput" style="display: none;" webkitdirectory directory multiple>
        `;
        
        // 重新获取元素并绑定事件（只有在重新创建HTML时才需要）
        const fileInput = document.getElementById('fileInput');
        const folderInput = document.getElementById('folderInput');
        
        fileInput.addEventListener('change', handleFileInputChange);
        folderInput.addEventListener('change', handleFolderInputChange);
    }
}

// 显示文件列表预览
function showFileListPreview() {
    const previewDiv = document.getElementById('fileListPreview');
    const fileListDiv = document.getElementById('fileList');
    const fileCountSpan = document.getElementById('fileCount');
    const totalSizeSpan = document.getElementById('totalSize');
    
    if (selectedFiles.length === 0) {
        hideFileListPreview();
        return;
    }
    
    // 按路径排序文件
    const sortedFiles = [...selectedFiles].sort((a, b) => {
        const pathA = a.webkitRelativePath || a.name;
        const pathB = b.webkitRelativePath || b.name;
        return pathA.localeCompare(pathB);
    });
    
    // 生成文件列表HTML
    fileListDiv.innerHTML = '';
    
    // 统计信息
    const totalSize = selectedFiles.reduce((sum, file) => sum + file.size, 0);
    const folderStructure = {};
    
    // 构建文件夹结构
    sortedFiles.forEach(file => {
        const path = file.webkitRelativePath || file.name;
        const pathParts = path.split('/');
        
        if (pathParts.length > 1) {
            const folderPath = pathParts.slice(0, -1).join('/');
            if (!folderStructure[folderPath]) {
                folderStructure[folderPath] = [];
            }
            folderStructure[folderPath].push(file);
        } else {
            if (!folderStructure['']) {
                folderStructure[''] = [];
            }
            folderStructure[''].push(file);
        }
    });
    
    // 渲染文件夹结构
    Object.keys(folderStructure).sort().forEach(folderPath => {
        if (folderPath) {
            // 添加文件夹标题
            const folderItem = document.createElement('div');
            folderItem.className = 'list-group-item list-group-item-secondary';
            folderItem.innerHTML = `
                <i class="bi bi-folder"></i>
                <strong>${folderPath}/</strong>
                <small class="text-muted">(${folderStructure[folderPath].length} 个文件)</small>
            `;
            fileListDiv.appendChild(folderItem);
        }
        
        // 添加文件
        folderStructure[folderPath].forEach(file => {
            const fileItem = document.createElement('div');
            fileItem.className = 'list-group-item';
            const fileName = file.name;
            const fileIcon = getFileIconForName(fileName);
            
            fileItem.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <i class="bi ${fileIcon}"></i>
                        <span class="ms-2">${fileName}</span>
                    </div>
                    <small class="text-muted">${formatFileSize(file.size)}</small>
                </div>
            `;
            fileListDiv.appendChild(fileItem);
        });
    });
    
    // 更新统计信息
    fileCountSpan.textContent = selectedFiles.length;
    totalSizeSpan.textContent = formatFileSize(totalSize);
    
    previewDiv.style.display = 'block';
}

// 隐藏文件列表预览
function hideFileListPreview() {
    document.getElementById('fileListPreview').style.display = 'none';
}

// 根据文件名获取图标
function getFileIconForName(fileName) {
    const ext = fileName.split('.').pop().toLowerCase();
    const iconMap = {
        'pdf': 'bi-file-earmark-pdf',
        'doc': 'bi-file-earmark-word',
        'docx': 'bi-file-earmark-word',
        'xls': 'bi-file-earmark-excel',
        'xlsx': 'bi-file-earmark-excel',
        'jpg': 'bi-file-earmark-image',
        'jpeg': 'bi-file-earmark-image',
        'png': 'bi-file-earmark-image',
        'gif': 'bi-file-earmark-image',
        'bmp': 'bi-file-earmark-image',
        'mp4': 'bi-file-earmark-play',
        'avi': 'bi-file-earmark-play',
        'mov': 'bi-file-earmark-play',
        'wmv': 'bi-file-earmark-play',
        'flv': 'bi-file-earmark-play',
        'mkv': 'bi-file-earmark-play',
        'txt': 'bi-file-earmark-text'
    };
    return iconMap[ext] || 'bi-file-earmark';
}

// 清除选择的文件
function clearSelectedFiles() {
    const fileInput = document.getElementById('fileInput');
    const folderInput = document.getElementById('folderInput');
    if (fileInput) fileInput.value = '';
    if (folderInput) folderInput.value = '';
    selectedFiles = [];
    updateUploadAreaDisplay();
    hideFileListPreview();
}

// 上传文件
async function uploadFile() {
    const description = document.getElementById('fileDescription').value.trim();
    const uploadType = document.querySelector('input[name="uploadType"]:checked').value;
    
    if (selectedFiles.length === 0) {
        showError('请选择要上传的文件');
        return;
    }
    
    try {
        document.getElementById('uploadProgress').style.display = 'block';
        document.getElementById('uploadBtn').disabled = true;
        document.getElementById('uploadStatus').textContent = '准备上传...';
        
        if (uploadType === 'folder' || selectedFiles.length > 1) {
            // 批量上传
            await uploadBatch(selectedFiles, description);
        } else {
            // 单文件上传
            await uploadSingleFile(selectedFiles[0], description);
        }
        
    } catch (error) {
        showError('上传失败: ' + error.message);
    } finally {
        document.getElementById('uploadProgress').style.display = 'none';
        document.getElementById('uploadBtn').disabled = false;
    }
}

// 单文件上传
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
    
    if (result.success) {
        showSuccess('文件上传成功');
        bootstrap.Modal.getInstance(document.getElementById('uploadModal')).hide();
        
        // 静默刷新，不显示提示
        await Promise.all([
            loadFileTree(),
            loadStats()
        ]);
    } else {
        throw new Error(result.error);
    }
}

// 批量上传
async function uploadBatch(files, description) {
    const formData = new FormData();
    
    // 添加文件
    files.forEach(file => {
        formData.append('files', file);
    });
    
    // 添加文件路径
    files.forEach(file => {
        const relativePath = file.webkitRelativePath || file.name;
        formData.append('file_paths[]', relativePath);
    });
    
    formData.append('description', description);
    if (currentParentId) {
        formData.append('parent_id', currentParentId);
    }
    
    document.getElementById('uploadStatus').textContent = `正在上传 ${files.length} 个文件...`;
    
    const response = await fetch('/api/upload/batch', {
        method: 'POST',
        body: formData
    });
    
    const result = await response.json();
    
    if (result.success) {
        const data = result.data;
        showSuccess(`批量上传完成！共上传 ${data.total_files} 个文件，创建 ${data.created_folders} 个文件夹`);
        bootstrap.Modal.getInstance(document.getElementById('uploadModal')).hide();
        
        // 重要：清理文件夹上传状态
        clearFolderUploadState();
        
        // 静默刷新，不显示提示
        await Promise.all([
            loadFileTree(),
            loadStats()
        ]);
    } else {
        throw new Error(result.error);
    }
}

// 清理文件夹上传状态
function clearFolderUploadState() {
    // 清除选中的文件
    selectedFiles = [];
    
    // 重置文件输入
    const fileInput = document.getElementById('fileInput');
    const folderInput = document.getElementById('folderInput');
    if (fileInput) fileInput.value = '';
    if (folderInput) folderInput.value = '';
    
    // 隐藏文件列表预览
    hideFileListPreview();
    
    // 重置上传类型为文件
    document.getElementById('uploadTypeFile').checked = true;
    document.getElementById('uploadTypeFolder').checked = false;
    
    console.log('文件夹上传状态已清理');
}

// 处理文档
async function processDocument(docId) {
    try {
        const response = await fetch(`/api/upload/process/${docId}`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('文档处理完成');
            showDocumentDetail({id: docId});
        } else {
            showError('文档处理失败: ' + result.error);
        }
    } catch (error) {
        showError('文档处理失败: ' + error.message);
    }
}

// 向量化文档
async function vectorizeDocument(docId) {
    try {
        // 首先预览PDF内容
        showInfo('正在分析PDF内容，请稍候...');
        
        const response = await fetch(`/api/vectorize/preview/${docId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                chunk_size: 1000,
                overlap: 200
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // 显示向量化预览模态框
            showVectorizationPreviewModal(result.data);
        } else {
            showError('PDF分析失败: ' + result.error);
        }
    } catch (error) {
        showError('PDF分析失败: ' + error.message);
    }
}

// 显示向量化预览模态框
function showVectorizationPreviewModal(data) {
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
    
    // 存储数据到模态框中
    document.getElementById('vectorizationModal').dataset.documentId = data.document_id;
    document.getElementById('vectorizationModal').dataset.originalData = JSON.stringify(data);
    
    modal.show();
}

// 渲染文本分段
function renderTextChunks(chunks) {
    const container = document.getElementById('chunksContainer');
    container.innerHTML = '';
    
    if (!chunks || !Array.isArray(chunks)) {
        container.innerHTML = '<div class="alert alert-warning">没有可显示的文本分段</div>';
        return;
    }
    
    chunks.forEach((chunk, index) => {
        // 安全地获取文本内容，避免undefined
        const content = chunk && chunk.content !== undefined && chunk.content !== null ? chunk.content : '';
        const chunkId = chunk && chunk.id ? chunk.id : `chunk_${index}`;
        
        const chunkDiv = document.createElement('div');
        chunkDiv.className = 'chunk-item mb-3';
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

// 重新分段
async function rechunkText() {
    try {
        const modal = document.getElementById('vectorizationModal');
        const documentId = modal.dataset.documentId;
        const chunkSize = parseInt(document.getElementById('chunkSize').value) || 1000;
        const overlap = parseInt(document.getElementById('chunkOverlap').value) || 200;
        
        showInfo('正在重新分段，请稍候...');
        
        const response = await fetch(`/api/vectorize/preview/${documentId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                chunk_size: chunkSize,
                overlap: overlap
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            // 更新分段显示
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

// 执行向量化
async function executeVectorization() {
    try {
        const modal = document.getElementById('vectorizationModal');
        const documentId = modal.dataset.documentId;
        const originalData = JSON.parse(modal.dataset.originalData);
        
        // 收集所有编辑后的文本块
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
        
        // 显示进度
        const executeBtn = document.getElementById('executeVectorization');
        const originalText = executeBtn.textContent;
        executeBtn.disabled = true;
        executeBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 向量化中...';
        
        showInfo('正在执行向量化，请稍候...');
        
        const response = await fetch(`/api/vectorize/execute/${documentId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                chunks: chunks,
                metadata: originalData.metadata
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess(`向量化完成！已处理 ${result.data.vectorized_chunks} 个文本块`);
            
            // 关闭模态框
            bootstrap.Modal.getInstance(modal).hide();
            
            // 刷新文档详情和统计信息
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
        // 恢复按钮状态
        const executeBtn = document.getElementById('executeVectorization');
        executeBtn.disabled = false;
        executeBtn.textContent = '确认向量化';
    }
}

// 现代化确认对话框
let confirmModalCallback = null;

function showConfirmModal(message, title = '确认操作', confirmText = '确定', confirmClass = 'btn-danger') {
    return new Promise((resolve) => {
        const modal = new bootstrap.Modal(document.getElementById('confirmModal'));
        
        // 设置内容
        document.getElementById('confirmModalTitle').innerHTML = `
            <i class="bi bi-exclamation-triangle-fill text-warning me-2"></i>
            ${title}
        `;
        document.getElementById('confirmModalMessage').innerHTML = message;
        
        // 设置确认按钮
        const confirmBtn = document.getElementById('confirmModalBtn');
        confirmBtn.textContent = confirmText;
        confirmBtn.className = `btn ${confirmClass}`;
        
        // 设置回调
        confirmModalCallback = resolve;
        
        // 显示模态框
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

// 监听模态框关闭事件
document.getElementById('confirmModal').addEventListener('hidden.bs.modal', function() {
    if (confirmModalCallback) {
        confirmModalCallback(false);
        confirmModalCallback = null;
    }
});

// 删除文档
async function deleteDocument(docId) {
    try {
        // 首先获取文档信息，检查是否有子项
        const checkResponse = await fetch(`/api/documents/${docId}/children`);
        const checkResult = await checkResponse.json();
        
        if (!checkResult.success) {
            showError('无法检查文档信息: ' + checkResult.error);
            return;
        }
        
        let confirmMessage = '确定要删除这个文档吗？<br><br><small class="text-muted">此操作不可撤销</small>';
        let confirmTitle = '删除文档';
        
        // 如果是文件夹且有子项，给出详细提示
        if (checkResult.data.has_children) {
            const childrenSummary = checkResult.data.children_summary.join('、');
            const totalItems = checkResult.data.total_descendants;
            
            confirmMessage = `
                <div class="alert alert-warning">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    <strong>警告：该文件夹不为空！</strong>
                </div>
                <p>该文件夹包含：<strong>${childrenSummary}</strong></p>
                <p>总共 <strong>${totalItems}</strong> 项内容</p>
                <p class="text-danger"><strong>删除文件夹将同时删除其中的所有内容！</strong></p>
                <p><small class="text-muted">此操作不可撤销，请谨慎操作。</small></p>
            `;
            confirmTitle = '删除文件夹及所有内容';
        }
        
        // 显示现代化确认对话框
        const confirmed = await showConfirmModal(confirmMessage, confirmTitle, '删除', 'btn-danger');
        
        if (!confirmed) {
            return;
        }
        
        // 执行删除
        const response = await fetch(`/api/documents/${docId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('文档删除成功');
            
            // 重要：重置UI状态
            resetSelectionAfterDelete();
            
            // 刷新数据和界面
            await loadFileTree();
            await loadStats();
            
        } else {
            showError('删除文档失败: ' + result.error);
        }
    } catch (error) {
        showError('删除文档失败: ' + error.message);
    }
}

// 删除后重置选择状态
function resetSelectionAfterDelete() {
    // 移除之前的选中状态
    document.querySelectorAll('.tree-item.selected').forEach(item => {
        item.classList.remove('selected');
    });
    
    // 重置全局状态
    selectedNode = null;
    currentParentId = null;
    
    // 重置路径显示
    updateCurrentPath(null);
    
    // 隐藏详情面板和搜索结果
    document.getElementById('documentDetail').style.display = 'none';
    document.getElementById('searchResults').style.display = 'none';
    
    // 重要：清理文件夹上传状态（如果存在）
    clearFolderUploadState();
}

// 加载统计信息
async function loadStats() {
    try {
        const response = await fetch('/api/search/stats');
        const result = await response.json();
        
        if (result.success) {
            const stats = result.data;
            
            document.getElementById('totalDocs').textContent = stats.document_stats.total_documents;
            document.getElementById('totalFolders').textContent = stats.document_stats.total_folders;
            document.getElementById('totalVectors').textContent = stats.vector_stats.total_entities || 0;
            document.getElementById('pdfCount').textContent = stats.document_stats.file_type_distribution.pdf || 0;
        }
    } catch (error) {
        console.error('加载统计信息失败:', error);
    }
}

// 工具函数
function getFileIcon(fileType) {
    const icons = {
        'pdf': 'bi-file-earmark-pdf',
        'word': 'bi-file-earmark-word',
        'excel': 'bi-file-earmark-excel',
        'image': 'bi-file-earmark-image',
        'video': 'bi-file-earmark-play'
    };
    return icons[fileType] || 'bi-file-earmark';
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

// Toast 通知系统
function showToast(message, type = 'success', duration = 3000) {
    const toastContainer = document.getElementById('toastContainer');
    
    // 创建唯一ID
    const toastId = 'toast-' + Date.now();
    
    // 根据类型设置图标
    const icons = {
        'success': 'bi-check-circle-fill',
        'error': 'bi-x-circle-fill',
        'warning': 'bi-exclamation-triangle-fill',
        'info': 'bi-info-circle-fill'
    };
    
    // 根据类型设置标题
    const titles = {
        'success': '成功',
        'error': '错误',
        'warning': '警告',
        'info': '信息'
    };
    
    // 创建Toast HTML
    const toastHTML = `
        <div id="${toastId}" class="toast ${type}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="toast-header">
                <i class="toast-icon ${icons[type]}"></i>
                <strong class="me-auto">${titles[type]}</strong>
                <button type="button" class="btn-close" onclick="hideToast('${toastId}')" aria-label="关闭"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    
    // 添加到容器
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    
    // 显示动画
    const toastElement = document.getElementById(toastId);
    toastElement.classList.add('show');
    
    // 自动隐藏
    setTimeout(() => {
        hideToast(toastId);
    }, duration);
    
    return toastId;
}

function hideToast(toastId) {
    const toastElement = document.getElementById(toastId);
    if (toastElement) {
        toastElement.classList.remove('show');
        toastElement.classList.add('hide');
        
        // 动画结束后移除元素
        setTimeout(() => {
            toastElement.remove();
        }, 300);
    }
}

function showSuccess(message) {
    showToast(message, 'success');
}

function showError(message) {
    showToast(message, 'error', 5000); // 错误消息显示更久
}

function showWarning(message) {
    showToast(message, 'warning', 4000);
}

function showInfo(message) {
    showToast(message, 'info');
}

// 显示编辑文档模态框
function showEditDocumentModal(docId, name, description, type) {
    document.getElementById('editDocumentId').value = docId;
    document.getElementById('editDocumentName').value = name;
    document.getElementById('editDocumentDescription').value = description || '';
    
    const title = type === 'folder' ? '编辑文件夹' : '编辑文件';
    document.getElementById('editDocumentTitle').textContent = title;
    
    const modal = new bootstrap.Modal(document.getElementById('editDocumentModal'));
    modal.show();
}

// 更新文档信息
async function updateDocument() {
    const docId = document.getElementById('editDocumentId').value;
    const name = document.getElementById('editDocumentName').value.trim();
    const description = document.getElementById('editDocumentDescription').value.trim();
    
    if (!name) {
        showError('名称不能为空');
        return;
    }
    
    try {
        const response = await fetch(`/api/documents/${docId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: name,
                description: description
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showSuccess('更新成功');
            bootstrap.Modal.getInstance(document.getElementById('editDocumentModal')).hide();
            loadFileTree();
            
            // 如果当前选中的是这个文档，刷新详情
            if (selectedNode && selectedNode.id == docId) {
                selectedNode.name = name;
                selectedNode.description = description;
                showDocumentDetail(selectedNode);
            }
        } else {
            showError('更新失败: ' + result.error);
        }
    } catch (error) {
        showError('更新失败: ' + error.message);
    }
}

// 显示文件夹右键菜单
async function showFolderContextMenu(event, node) {
    // 显示现代化确认对话框
    const confirmed = await showConfirmModal(
        `是否编辑文件夹 "<strong>${node.name}</strong>"？`, 
        '编辑文件夹', 
        '编辑', 
        'btn-primary'
    );
    
    if (confirmed) {
        showEditDocumentModal(node.id, node.name, node.description || '', 'folder');
    }
}

// 显示创建顶级文件夹模态框
function showCreateRootFolderModal() {
    document.getElementById('folderName').value = '';
    document.getElementById('folderDescription').value = '';
    
    // 设置为创建顶级文件夹模式
    currentParentId = null;
    
    const modal = new bootstrap.Modal(document.getElementById('createFolderModal'));
    const title = document.querySelector('#createFolderModal .modal-title');
    title.textContent = '创建顶级文件夹';
    
    modal.show();
}

// 重置选择状态（用于创建顶级文件夹后）
function resetSelection() {
    // 移除之前的选中状态
    document.querySelectorAll('.tree-item.selected').forEach(item => {
        item.classList.remove('selected');
    });
    
    selectedNode = null;
    currentParentId = null;
    
    // 重置路径显示
    updateCurrentPath(null);
    
    // 隐藏详情面板
    document.getElementById('documentDetail').style.display = 'none';
    document.getElementById('searchResults').style.display = 'none';
}

// 调试函数：显示当前状态信息
function debugCurrentState() {
    const stateInfo = {
        selectedNode: selectedNode,
        currentParentId: currentParentId,
        documentDetailVisible: document.getElementById('documentDetail').style.display !== 'none',
        searchResultsVisible: document.getElementById('searchResults').style.display !== 'none',
        selectedTreeItems: document.querySelectorAll('.tree-item.selected').length
    };
    
    console.log('当前UI状态:', stateInfo);
    
    // 在Toast中显示简要信息
    const parentInfo = currentParentId ? `当前父文件夹ID: ${currentParentId}` : '当前在根目录';
    const nodeInfo = selectedNode ? `选中节点: ${selectedNode.name} (ID: ${selectedNode.id})` : '无选中节点';
    showInfo(`状态检查 - ${parentInfo}, ${nodeInfo}`);
    
    return stateInfo;
} 