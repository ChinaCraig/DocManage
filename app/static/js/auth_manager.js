/**
 * 前端认证管理组件
 * 负责处理用户认证、权限检查、会话管理等
 */
class AuthManager {
    constructor() {
        this.currentUser = null;
        this.authEnabled = false;
        this.authenticated = false;
        this.checkInterval = null;
        
        this.init();
    }

    async init() {
        try {
            await this.checkAuthStatus();
            this.startSessionCheck();
            this.bindEvents();
        } catch (error) {
            console.error('认证管理器初始化失败:', error);
        }
    }

    /**
     * 检查认证状态
     */
    async checkAuthStatus() {
        try {
            const response = await fetch('/api/auth/check-auth');
            const data = await response.json();
            
            if (data.success) {
                this.authEnabled = data.auth_enabled;
                this.authenticated = data.authenticated || false;
                this.currentUser = data.user || null;
                
                // 触发认证状态变更事件
                this.dispatchAuthEvent('auth-status-changed', {
                    authEnabled: this.authEnabled,
                    authenticated: this.authenticated,
                    user: this.currentUser
                });
                
                return data;
            } else {
                throw new Error(data.message || '检查认证状态失败');
            }
        } catch (error) {
            console.error('检查认证状态失败:', error);
            this.authEnabled = false;
            this.authenticated = false;
            this.currentUser = null;
            return null;
        }
    }

    /**
     * 用户登录
     */
    async login(username, password, rememberMe = false) {
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username: username,
                    password: password,
                    remember_me: rememberMe
                })
            });

            const result = await response.json();

            if (result.success) {
                this.authenticated = true;
                this.currentUser = result.user;
                
                // 触发登录成功事件
                this.dispatchAuthEvent('login-success', {
                    user: this.currentUser,
                    message: result.message
                });
                
                return result;
            } else {
                // 触发登录失败事件
                this.dispatchAuthEvent('login-failed', {
                    message: result.message
                });
                
                return result;
            }
        } catch (error) {
            console.error('登录请求失败:', error);
            return { success: false, message: '网络错误，请稍后重试' };
        }
    }

    /**
     * 用户登出
     */
    async logout() {
        try {
            const response = await fetch('/api/auth/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            const result = await response.json();

            // 无论服务器返回什么，都清除本地状态
            this.authenticated = false;
            this.currentUser = null;
            
            // 触发登出事件
            this.dispatchAuthEvent('logout', {
                message: result.message || '已登出'
            });

            return result;
        } catch (error) {
            console.error('登出请求失败:', error);
            // 即使请求失败，也清除本地状态
            this.authenticated = false;
            this.currentUser = null;
            this.dispatchAuthEvent('logout', {
                message: '已登出'
            });
        }
    }

    /**
     * 获取当前用户信息
     */
    async getCurrentUser() {
        if (!this.authEnabled) {
            return null;
        }

        try {
            const response = await fetch('/api/auth/current-user');
            const result = await response.json();

            if (result.success) {
                this.currentUser = result.user;
                return result.user;
            } else {
                this.currentUser = null;
                this.authenticated = false;
                return null;
            }
        } catch (error) {
            console.error('获取用户信息失败:', error);
            return null;
        }
    }

    /**
     * 检查用户权限
     */
    hasPermission(permission) {
        if (!this.authEnabled) {
            return true; // 未启用认证时，允许所有操作
        }

        if (!this.authenticated || !this.currentUser) {
            return false;
        }

        // 管理员拥有所有权限
        if (this.currentUser.is_admin) {
            return true;
        }

        // 检查具体权限（需要从服务器获取权限信息）
        return this.currentUser.permissions?.[permission] || false;
    }

    /**
     * 要求认证
     */
    requireAuth() {
        if (!this.authEnabled) {
            return true;
        }

        if (!this.authenticated) {
            this.redirectToLogin();
            return false;
        }

        return true;
    }

    /**
     * 要求权限
     */
    requirePermission(permission) {
        if (!this.requireAuth()) {
            return false;
        }

        if (!this.hasPermission(permission)) {
            this.showPermissionDenied();
            return false;
        }

        return true;
    }

    /**
     * 跳转到登录页面
     */
    redirectToLogin() {
        const currentUrl = encodeURIComponent(window.location.href);
        window.location.href = `/api/auth/login-page?redirect=${currentUrl}`;
    }

    /**
     * 显示权限不足提示
     */
    showPermissionDenied() {
        this.dispatchAuthEvent('permission-denied', {
            message: '权限不足，无法执行此操作'
        });
    }

    /**
     * 启动会话检查
     */
    startSessionCheck() {
        // 每5分钟检查一次会话状态
        this.checkInterval = setInterval(() => {
            this.checkAuthStatus();
        }, 5 * 60 * 1000);
    }

    /**
     * 停止会话检查
     */
    stopSessionCheck() {
        if (this.checkInterval) {
            clearInterval(this.checkInterval);
            this.checkInterval = null;
        }
    }

    /**
     * 绑定全局事件
     */
    bindEvents() {
        // 监听页面关闭事件
        window.addEventListener('beforeunload', () => {
            this.stopSessionCheck();
        });

        // 监听认证相关的自定义事件
        document.addEventListener('auth-required', (event) => {
            if (!this.requireAuth()) {
                event.preventDefault();
                event.stopPropagation();
            }
        });

        document.addEventListener('permission-required', (event) => {
            const permission = event.detail?.permission;
            if (permission && !this.requirePermission(permission)) {
                event.preventDefault();
                event.stopPropagation();
            }
        });
    }

    /**
     * 触发认证事件
     */
    dispatchAuthEvent(eventType, detail = {}) {
        const event = new CustomEvent(eventType, {
            detail: detail,
            bubbles: true,
            cancelable: true
        });
        document.dispatchEvent(event);
    }

    /**
     * API请求拦截器
     */
    async apiRequest(url, options = {}) {
        // 添加认证检查
        if (this.authEnabled && !this.authenticated) {
            throw new Error('未登录');
        }

        // 添加默认headers
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        try {
            const response = await fetch(url, defaultOptions);
            
            // 检查是否需要重新登录
            if (response.status === 401) {
                this.authenticated = false;
                this.currentUser = null;
                this.dispatchAuthEvent('session-expired', {
                    message: '会话已过期，请重新登录'
                });
                return null;
            }

            return response;
        } catch (error) {
            console.error('API请求失败:', error);
            throw error;
        }
    }

    /**
     * 销毁认证管理器
     */
    destroy() {
        this.stopSessionCheck();
        this.currentUser = null;
        this.authenticated = false;
        this.authEnabled = false;
    }
}

/**
 * 认证装饰器函数
 */
function requireAuth(target, propertyName, descriptor) {
    const method = descriptor.value;
    
    descriptor.value = function(...args) {
        if (!window.authManager.requireAuth()) {
            return;
        }
        return method.apply(this, args);
    };
    
    return descriptor;
}

function requirePermission(permission) {
    return function(target, propertyName, descriptor) {
        const method = descriptor.value;
        
        descriptor.value = function(...args) {
            if (!window.authManager.requirePermission(permission)) {
                return;
            }
            return method.apply(this, args);
        };
        
        return descriptor;
    };
}

/**
 * 工具函数
 */
const AuthUtils = {
    /**
     * 检查是否需要认证
     */
    needsAuth() {
        return window.authManager?.authEnabled || false;
    },

    /**
     * 获取当前用户
     */
    getCurrentUser() {
        return window.authManager?.currentUser || null;
    },

    /**
     * 检查是否已登录
     */
    isAuthenticated() {
        return window.authManager?.authenticated || false;
    },

    /**
     * 检查权限
     */
    hasPermission(permission) {
        return window.authManager?.hasPermission(permission) || false;
    },

    /**
     * 格式化用户显示名称
     */
    formatUserDisplayName(user) {
        if (!user) return '未知用户';
        return user.real_name || user.username || '未知用户';
    },

    /**
     * 获取用户头像URL（可扩展）
     */
    getUserAvatarUrl(user) {
        if (!user) return '/static/images/default-avatar.png';
        // 可以扩展为使用Gravatar或其他头像服务
        return `/static/images/avatar/${user.id}.png`;
    }
};

// 全局初始化
document.addEventListener('DOMContentLoaded', () => {
    window.authManager = new AuthManager();
});

// 导出到全局
window.AuthManager = AuthManager;
window.AuthUtils = AuthUtils;
window.requireAuth = requireAuth;
window.requirePermission = requirePermission; 