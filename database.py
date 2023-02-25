from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String
from flask_sqlalchemy import SQLAlchemy
import psycopg2

DATABASE_URL = "postgresql://virtuallyme_db_user:V3qyWKGBmuwpH0To2o5eVkqa1X4nqMhR@dpg-cfskiiarrk00vm1bp320-a.singapore-postgres.render.com/virtuallyme_db" #external

engine = create_engine(DATABASE_URL)


