# 数据库脚本使用说明

## 脚本整理结果

已将项目中的MySQL脚本整理合并为一个完整的脚本文件：

### 原始脚本文件：
- `create_tables.sql` - 基础表结构创建脚本
- `add_vectorization_fields.sql` - 向量化字段添加脚本

### 合并后的脚本：
- `merged_database_setup.sql` - **完整的数据库设置脚本**

## 新脚本的优势

1. **一次性执行**：无需分别执行多个脚本文件
2. **完整性**：包含所有表结构、字段、索引和默认数据
3. **避免冲突**：已整合向量化字段到基础表结构中
4. **验证功能**：自动验证数据库设置结果

## 使用方法

### 方法一：命令行执行
```bash
# 1. 创建数据库
mysql -h 192.168.16.199 -u root -p -e "CREATE DATABASE document_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. 执行脚本
mysql -h 192.168.16.199 -u root -p document_management < database/merged_database_setup.sql
```

### 方法二：MySQL客户端执行
```sql
-- 1. 连接到MySQL
mysql -h 192.168.16.199 -u root -p

-- 2. 创建数据库
CREATE DATABASE document_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 3. 使用数据库
USE document_management;

-- 4. 执行脚本
source /path/to/database/merged_database_setup.sql;
```

## 脚本包含的内容

### 数据表结构
1. `document_nodes` - 文档节点表（包含向量化字段）
2. `document_contents` - 文档内容表
3. `vector_records` - 向量化记录表
4. `tags` - 标签表
5. `document_tags` - 文档标签关联表
6. `system_configs` - 系统配置表

### 默认数据
- 系统配置项（包含基础配置和向量化配置）
- 默认标签数据

### 验证功能
- 表结构验证
- 配置数据确认
- 索引创建确认
- 执行状态报告

## 建议

1. **备份现有数据库**：如果有现有数据，请先备份
2. **测试环境验证**：建议先在测试环境执行
3. **权限确认**：确保MySQL用户有足够的权限
4. **查看执行结果**：脚本会输出详细的验证信息

## 文件清理

执行新脚本后，可以考虑将原始的分散脚本文件移动到备份目录：
```bash
mkdir database/backup
mv database/create_tables.sql database/backup/
mv database/add_vectorization_fields.sql database/backup/
``` 