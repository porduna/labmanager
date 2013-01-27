# -*-*- encoding: utf-8 -*-*-
#
# lms4labs is free software: you can redistribute it and/or modify
# it under the terms of the BSD 2-Clause License
# lms4labs is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

"""
  :copyright: 2012 Pablo Orduña, Elio San Cristobal, Alberto Pesquera Martín
  :license: BSD, see LICENSE for more details
"""

import json
import hashlib

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from config import SQLALCHEMY_ENGINE_STR, USE_PYMYSQL

if USE_PYMYSQL:
    import pymysql_sa
    pymysql_sa.make_default_mysql_dialect()

engine = create_engine(SQLALCHEMY_ENGINE_STR, convert_unicode=True, pool_recycle=3600)

db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def init_db(drop = False):
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
    # you will have to import them first before calling init_db()
    import labmanager.models
    assert labmanager.models != None # pyflakes ignore

    if drop:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

def add_sample_users():
    from labmanager.models import LMS, LabManagerUser, Course, PermissionOnCourse, PermissionOnLaboratory, Laboratory
    from labmanager.models import NewLMS, RLMS, Permission, Credential, NewCourse

    init_db(drop = True)
    password = unicode(hashlib.new('sha', 'password').hexdigest())

#     lms1 = LMS(u'Universidad Nacional de Educacion a Distancia',
#                u"http://localhost:5000/fake_list_courses/lms4labs/list",
#                u'uned',
#                password,
#                u"labmanager",
#                u"password" )
#     db_session.add(lms1)
# 
#     lms2 = LMS(u'Universidad de Deusto',
#                u"http://localhost:5000/fake_list_courses/lms4labs/list",
#                u'deusto',
#                password,
#                u"labmanager",
#                u"password" )
#     db_session.add(lms2)
# 
#     lms3 = LMS(u'Moodle Test',
#                u'http://localhost:8888/moodle/blocks/lms4labs/lms/list.php',
#                u'admin',
#                u'80072568beb3b2102325eb203f6d0ff92f5cef8e',
#                u'admin',
#                u'password' )
#     db_session.add(lms3)
# 
# 
    user6 = LabManagerUser(u'admin', u'Administrator', password, 'admin')
    db_session.add(user6)

#     course1 = Course(lms1, u"1", u"my course 1")
#     db_session.add(course1)
# 
#     course2 = Course(lms2, u"2", u"my course 2")
#     db_session.add(course2)


    configuration = {
        'remote_login' : 'weblabfed',
        'password'     : 'password',
        'base_url'     : 'http://www.weblab.deusto.es/weblab/',
    }

    rlms1 = RLMS(kind = u"WebLab-Deusto",
                       location = u"Deusto Spain",
                       url = u"https://www.weblab.deusto.es/",
                       version = u"5.0",
                       configuration = json.dumps(configuration) )
    db_session.add(rlms1)

    rlms2 = RLMS(kind = u'iLabs',
                       location = u'MIT',
                       url = u'http://ilab.mit.edu/wiki/',
                       version = u"1.2.2")
    db_session.add(rlms2)



    robot_lab = Laboratory(name = u"robot-movement@Robot experiments",
                           laboratory_id = u"robot-movement@Robot experiments",
                           rlms = rlms1)
# 
#     permission_on_uned = PermissionOnLaboratory(lms = lms1,
#                                                 laboratory = robot_lab,
#                                                 configuration = u"{}",
#                                                 local_identifier = u"robot")
#     permission_on_deusto = PermissionOnLaboratory(lms = lms2,
#                                                   laboratory = robot_lab,
#                                                   configuration = u"{}",
#                                                   local_identifier = u"robot")
# 
#     db_session.add(permission_on_uned)
#     db_session.add(permission_on_deusto)
# 
#     permission_on_course1 = PermissionOnCourse(permission_on_lab = permission_on_uned,
#                                                course = course1,
#                                                configuration = u"{}")
#     permission_on_course2 = PermissionOnCourse(permission_on_lab = permission_on_deusto,
#                                                course = course2,
#                                                configuration = u"{}")
# 
#     db_session.add(permission_on_course1)
#     db_session.add(permission_on_course2)


    newlms1 = NewLMS(name = u"My Moodle",
                     url = u"http://moodle.com.co.co")
    db_session.add(newlms1)

    course1 = NewCourse(name = u"EE101",
                        lms = newlms1,
                        context_id = u"1")
    db_session.add(course1)

    permission_to_lms1 = PermissionOnLaboratory(lms = newlms1, laboratory = robot_lab, configuration = '', local_identifier = 'robot')

    permission1 = Permission(context = course1,
                             permission_on_lab = permission_to_lms1,
                             access = u"pending")
    db_session.add(permission1)

    auth1 = Credential(key = u"admin",
                      kind = u"OAuth1.0",
                      secret = u"80072568beb3b2102325eb203f6d0ff92f5cef8e",
                      lms = newlms1)
    db_session.add(auth1)

    db_session.commit()
