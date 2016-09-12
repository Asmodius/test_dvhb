DROP TABLE IF EXISTS node;

CREATE TABLE node (
    id serial PRIMARY KEY,
    text varchar(255),
    path varchar(255)
);
