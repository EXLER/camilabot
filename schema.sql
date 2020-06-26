CREATE TABLE events
(
    event_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    creator_id      INTEGER,
    event_title     TEXT,
    event_date      TEXT,
    event_group     TEXT
);