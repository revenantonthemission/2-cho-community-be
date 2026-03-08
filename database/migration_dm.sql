-- DM 대화 테이블
CREATE TABLE IF NOT EXISTS dm_conversation (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    participant1_id INT UNSIGNED NOT NULL,
    participant2_id INT UNSIGNED NOT NULL,
    last_message_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    UNIQUE KEY uq_conversation_pair (participant1_id, participant2_id),
    FOREIGN KEY (participant1_id) REFERENCES user(id),
    FOREIGN KEY (participant2_id) REFERENCES user(id),
    INDEX idx_conv_participant1 (participant1_id, deleted_at, last_message_at DESC),
    INDEX idx_conv_participant2 (participant2_id, deleted_at, last_message_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- DM 메시지 테이블
CREATE TABLE IF NOT EXISTS dm_message (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT UNSIGNED NOT NULL,
    sender_id INT UNSIGNED NOT NULL,
    content TEXT NOT NULL,
    is_read TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES dm_conversation(id),
    FOREIGN KEY (sender_id) REFERENCES user(id),
    INDEX idx_msg_conversation (conversation_id, created_at),
    INDEX idx_msg_unread (conversation_id, sender_id, is_read)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
