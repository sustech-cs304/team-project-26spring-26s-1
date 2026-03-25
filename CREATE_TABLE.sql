-- Skills Hub 数据库表结构 (SQLite)
-- 执行: sqlite3 skills_hub.db < CREATE_TABLE.sql

-- 用户表
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    username TEXT NOT NULL,
    role TEXT DEFAULT 'user',  -- user, admin
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 邮箱验证码表
CREATE TABLE IF NOT EXISTS email_verifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    code TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_verification_email ON email_verifications (email);
CREATE INDEX IF NOT EXISTS idx_verification_timestamp ON email_verifications (created_at);

-- 技能表
CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    markdown_content TEXT NOT NULL,
    user_id INTEGER REFERENCES users(id),
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected, archived
    rejection_reason TEXT,
    download_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_skills_status ON skills (status);
CREATE INDEX IF NOT EXISTS idx_skills_user ON skills (user_id);

-- 标签表
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

-- 技能-标签关联表
CREATE TABLE IF NOT EXISTS skill_tags (
    skill_id INTEGER REFERENCES skills(id) ON DELETE CASCADE,
    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (skill_id, tag_id)
);

-- 插入默认管理员账户 (密码: admin123)
-- 密码已通过 hash_password() 处理 (salt: change-me-in-production)
INSERT OR IGNORE INTO users (email, password, username, role) VALUES
('admin@edu.cn', 'fb189086a928fa32d5d1bcfd3a63804e290623101cb6cb4c1bfd636136448145', 'Administrator', 'admin');

-- 插入预设标签
INSERT OR IGNORE INTO tags (name) VALUES 
('编程辅助'), ('数据分析'), ('文档生成'), ('图像处理'), ('自然语言处理'), ('自动化'), ('机器学习'), ('Web开发');

