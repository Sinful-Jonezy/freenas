#+
# Copyright 2014 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

import errno
import inspect
import logging
import traceback


class RpcContext(object):
    def __init__(self):
        self.logger = logging.getLogger('RpcContext')
        self.services = {}
        self.instances = {}
        self.schema_definitions = {}
        self.register_service('discovery', DiscoveryService)

    def register_service(self, name, clazz):
        self.services[name] = clazz
        self.instances[name] = clazz()
        self.instances[name].initialize(self)

    def register_service_instance(self, name, instance):
        self.services[name] = instance.__class__
        self.instances[name] = instance

    def unregister_service(self, name):
        if not name in self.services.keys():
            return

        del self.instances[name]
        del self.services[name]

    def register_schema_definition(self, name, definition):
        self.schema_definitions[name] = definition

    def get_service(self, name):
        if name not in self.instances.keys():
            return None

        return self.instances[name]

    def dispatch_call(self, method, args, sender=None):
        service, sep, name = method.rpartition(".")
        self.logger.info('Call: service=%s, method=%s', service, method)

        if args is None:
            args = {}

        if not service:
            raise RpcException(errno.EINVAL, "Invalid function path")

        if service not in self.services.keys():
            raise RpcException(errno.ENOENT, "Service {0} not found".format(service))

        try:
            func = getattr(self.instances[service], name)
        except AttributeError:
            raise RpcException(errno.ENOENT, "Method not found")

        if hasattr(func, 'required_roles'):
            for i in func.required_roles:
                if not self.user.has_role(i):
                    self.emit_rpc_error(id, errno.EACCES, 'Insufficent privileges')
                    return

        if hasattr(func, 'pass_sender'):
            if type(args) is dict:
                args['sender'] = sender
            elif type(args) is list:
                args.append(sender)

        try:
            if type(args) is dict:
                result = func(**args)
            elif type(args) is list:
                result = func(*args)
            else:
                raise RpcException(errno.EINVAL, "Function parameters should be passed as dictionary or array")
        except Exception, err:
            raise RpcException(errno.EFAULT, traceback.format_exc())

        self.instances[service].sender = None
        return result

    def build_schema(self):
        for name, definition in self.schema_definitions.items():
            pass


class RpcService(object):
    @classmethod
    def _get_metadata(self):
        return None

    def _build_params_schema(self, method):
        return {
            'type': 'array',
            'items': method.params_schema
        }

    def _build_result_schema(self, method):
        return method.result_schema

    def enumerate_methods(self):
        methods = []
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith('_'):
                continue

            if name in (
                'initialize',
                'enumerate_methods'):
                continue

            result = {'name': name}

            if hasattr(method, 'description'):
                result['description'] = method.description

            if hasattr(method, 'params_schema'):
                result['params-schema'] = self._build_params_schema(method)

            if hasattr(method, 'result_schema'):
                result['result-schema'] = self._build_result_schema(method)


            methods.append(result)

        return methods


class RpcException(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        self.stacktrace = traceback.format_exc()

    def __str__(self):
        return "{}: {}".format(errno.errorcode[self.code], self.message)


class DiscoveryService(RpcService):
    def __init__(self):
        self.__context = None

    def initialize(self, context):
        self.__context = context

    def get_services(self):
        return self.__context.services.keys()

    def get_tasks(self):
        return {n: x._get_metadata() for n, x in self.__context.dispatcher.tasks.items()}

    def get_methods(self, service):
        if not service in self.__context.services.keys():
            raise RpcException(errno.ENOENT, "Service not found")

        return list(self.__context.instances[service].enumerate_methods())

    def get_schema(self):
        return {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'id': 'http://freenas.org/schema/v10#',
            'type': 'object',
            'definitions': self.__context.schema_definitions
        }


def description(descr):
    def wrapped(fn):
        fn.description = descr
        return fn

    return wrapped


def accepts(*sch):
    def wrapped(fn):
        fn.params_schema = sch
        return fn

    return wrapped


def returns(*sch):
    def wrapped(fn):
        fn.result_schema = sch
        return fn

    return wrapped


def require_roles(*roles):
    def wrapped(fn):
        fn.roles_required = roles
        return fn

    return wrapped


def pass_sender(fn):
    fn.pass_sender = True
    return fn