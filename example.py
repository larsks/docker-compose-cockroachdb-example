from contextlib import contextmanager

import logging
import logging.config
import os
import time

import fastapi
import psycopg
import dotenv

dotenv.load_dotenv()

try:
    logging.config.fileConfig("logging.conf", disable_existing_loggers=False)
except FileNotFoundError:
    logging.basicConfig(level="INFO")

log = logging.getLogger(__name__)
dbname = os.getenv("EXAMPLE_DB_NAME", "example")
dbuser = os.getenv("EXAMPLE_DB_USER", "root")
dbhost = os.getenv("EXAMPLE_DB_HOST", "localhost")
dbport = os.getenv("EXAMPLE_DB_PORT", "5432")


@contextmanager
def get_db_connection():
    with psycopg.connect(dbname=dbname, user=dbuser, host=dbhost, port=dbport) as conn:
        yield conn


def is_init_complete():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "select state from distributed_locks where name='init_completed'"
            )
            res = cursor.fetchone()
            return res[0] == 1
        except psycopg.errors.Error as err:
            return False


def initialize_database():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"create database {dbname}")
            cursor.execute(
                "create table distributed_locks (name varchar(20), state int)"
            )

            cursor.execute(
                "insert into distributed_locks (name, state) values (%s, %s)",
                ("init_completed", 1),
            )
    except psycopg.errors.DuplicateDatabase:
        while not is_init_complete():
            log.info("waiting for database initialization to complete")
            time.sleep(1)

    log.info("database initialization complete")


def create_app():
    app = fastapi.FastAPI()

    if not is_init_complete():
        log.warning("attempting database initialization")
        initialize_database()

    @app.get("/")
    def root():
        return "Everything is a-okay"

    return app


app = create_app()
