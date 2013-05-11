#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Guifibages sso provider
#
# Copyright 2012 Associació d'Usuaris Guifibages
# Author: Ignacio Torres Masdeu <ignacio@xin.cat>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.



import ldap
import ldap.modlist as modlist

import copy
from base64 import urlsafe_b64encode, b64encode
from random import randint
from datetime import datetime, timedelta
from flask import Flask, url_for, request, Response, json
app = Flask(__name__)

def validate_login(request):
    try:
        username = request.form['username']
        password = request.form['password']
        if len(username)==0:
            return response({'error': 'Invalid credentials'} ,status=401)
    except KeyError, error:
        print "KeyError %s" % request.form
        return Response('Wrong request' ,status=400)
    user_dn = "uid=%s,ou=Users,ou=auth,dc=guifibages,dc=net" % username
    l = ldap_bind(user_dn, password)
    return (user_dn, l, username, password)

def modify_ldap_property(l, modified_dn, old, new):
    try:
        ldif = modlist.modifyModlist(old, new)    
        l.modify_s(modified_dn, ldif)
        return (True, None)
    except ldap.INSUFFICIENT_ACCESS:
        error = {"code": 401, "error": "Insufficient access", "action": new}
        return (False, error)
    except:
        raise
        return False

def ldap_bind(binddn, password):
    l = ldap.initialize("ldaps://aaa.guifibages.net:636")
    l.simple_bind_s(binddn,password)
    return l
    """
    try:
        l = ldap.initialize("ldaps://aaa.guifibages.net:636")
        l.simple_bind_s(binddn,password)
        return l
    except ldap.INVALID_CREDENTIALS:
        return response({'error': 'Invalid credentials'} ,status=401)
    except ldap.SERVER_DOWN:
        return response({'error': "Can't connect to server"} ,status=500)
    except ldap.LDAPError, error_message:
        print "Excepcion: %s" % error_message
        return response({'error': "LDAPError: %s" % error_message} ,status=500)
    """
def generate_otp():
    """Return a 6 digits random One Time Password"""
    return "%06d" % randint(1,999999)

def read_pac(view="internet"):
    """Read the specified pac file from disk and return it as a string

    Arguments:
    view -- the intended view (default: "internet")
    """
    try:
        with open('static/%s-pac.js' % view,'r') as pac_file:
            return pac_file.read()
    except IOError, e:
        if e.errno == 2:
            return


# We use this as an argument to json.dumps to convert datetime objects to json
dthandler = lambda obj: obj.isoformat() if isinstance(obj, datetime) else None


def response(msg, status=200):
    return Response(json.dumps(msg, default=dthandler), status=status)

def get_request_ip(request):
    if not request.headers.getlist("X-Forwarded-For"):
       ip = request.remote_addr
    else:
       ip = request.headers.getlist("X-Forwarded-For")[0]
    return ip

def is_trusted_server(ip):
    servers = ['10.228.17.24', '10.228.17.29']
    return ip in servers

@app.route('/api/user/<username>/otp', methods = ['POST'])
def validate_otp(username):
    if not 'password' in request.form or not 'ip' in request.form:
        return response({'error': 'Invalid credentials'} ,status=401)
    password = request.form['password']
    ip = request.form['ip']

    if not ip in sessions[username]:
        return response({'error': 'Invalid IP'} ,status=401)
    if password != sessions[username][ip]['otp']:
        return response({'error': 'Invalid credentials'} ,status=401)
    return response(True)


@app.route('/api/user/<username>', methods = ['GET'])
def user_info(username):
    global sessions
    user_dn, l, username, password = validate_login(request)

@app.route('/api/user/<updated_user>/update', methods = ['POST'])
def update_user(updated_user):
    result = {}
    try:
        user_dn, l, username, password = validate_login(request)
    except ldap.INVALID_CREDENTIALS:
        return response({'error': 'Invalid credentials'} ,status=401)
    except ldap.SERVER_DOWN:
        return response({'error': "Can't connect to server"} ,status=500)
    except:
        return response({'error': "shit happened"}, 500)
    update_dn = "uid=%s,ou=Users,ou=auth,dc=guifibages,dc=net" % updated_user
    original_record = l.search_s(update_dn, ldap.SCOPE_BASE, 'objectClass=*')[0][1]
    modified_record = copy.deepcopy(original_record)

    for field in request.form:
        if field in ['username', 'password']:
            continue
        new_value = str(request.form[field])
        if field not in original_record or original_record[field] != new_value and new_value not in original_record[field]:
            modified_record[field] = new_value

    if original_record == modified_record:
        return response("No changes")

    result['original_record'] = original_record
    result['modified_record'] = modified_record
    modified, error = modify_ldap_property(l, update_dn, original_record, modified_record)
    if modified:
        return response(result)
    else:
        return response(error, error['code'])

@app.route('/api/login', methods = ['POST'])
def login():
    global sessions
    result = {}
    try:
        user_dn, l, username, password = validate_login(request)
    except ldap.INVALID_CREDENTIALS:
        return response({'error': 'Invalid credentials'} ,status=401)
    except ldap.SERVER_DOWN:
        return response({'error': "Can't connect to server"} ,status=500)
    except:
        return response({'error': "shit happened"}, 500)

    ip = get_request_ip(request)
    
    if not username in sessions:
            sessions[username] = {}
    result['otp'] = generate_otp()
    result['ts'] = datetime.now()
    sessions[username][ip] = result
    # We add the pac after saving the result to the session
    if ip[0:3] != '10.':
        result['pac'] = read_pac('internet')
    return response(result)

if __name__ == "__main__":
    global sessions
    sessions = dict()
    app.run(debug=True)
