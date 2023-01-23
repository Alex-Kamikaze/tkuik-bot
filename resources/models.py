from sqlalchemy import Column, Float, String, create_engine, Integer, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

Base = declarative_base()
db = create_engine('sqlite:///subs.db')

Base.metadata.bind = db

class Auth(Base):
    __tablename__ = 'auth'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable = False)
    group_id = Column(Integer, ForeignKey("groups.id"))
    notification = Column(Boolean, default = True)
    hour = Column(Integer, nullable = False, default = 7)
    minute = Column(Integer, nullable = False, default = 0)
    group = relationship("Group", back_populates = "auths")

class Substitution(Base):
    __tablename__ = 'substitutions'
    id = Column(Integer, primary_key = True)
    file_id = Column(Integer, ForeignKey("parsed.id"))
    pair_num = Column(Integer)
    init_pair = Column(String, nullable=False)
    sub_pair = Column(String, nullable=False)
    cab = Column(Integer)
    group_id = Column(Integer, ForeignKey("groups.id"))
    group = relationship("Group", back_populates = "subs")
    file = relationship("ParsedFiles", back_populates = "subs")

class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    group_name = Column(String)
    grade = Column(Integer, default = None)
    auths = relationship("Auth", back_populates = "group")
    subs = relationship("Substitution", cascade = "all,delete", back_populates = "group")
    timetable = relationship("Timetable", back_populates = "group")

class ParsedFiles(Base):
    __tablename__ = "parsed"
    id = Column(Integer, primary_key = True)
    filename = Column(String, unique = True)
    subs = relationship("Substitution", cascade = "all,delete", back_populates = "file")

class Timetable(Base):
    __tablename__ = "timetable"
    id = Column(Integer, primary_key = True)
    group_id = Column(Integer, ForeignKey("groups.id"))
    pair_num = Column(Integer)
    pair_name = Column(String, nullable=False)
    cab = Column(Integer)
    week_day_num = Column(Integer)
    denominator = Column(Integer, nullable = True, default = None)
    group = relationship("Group", back_populates = "timetable")


session_meta = sessionmaker(autoflush=False, bind=db)
session = session_meta()