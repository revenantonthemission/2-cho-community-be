-- @멘션 알림 타입 추가
ALTER TABLE notification MODIFY COLUMN type ENUM('comment', 'like', 'mention') NOT NULL;
