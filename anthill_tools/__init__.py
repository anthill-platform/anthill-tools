
import requests
import json
import urllib


def log(s):
    print s


def get(url, params=None, **kwargs):
    try:
        response = requests.get(url, params=params, **kwargs)
    except requests.ConnectionError as e:
        raise ServiceError(599, e.message)

    if response.status_code >= 300:
        raise ServiceError(response.status_code, response.text, response)

    return response


def post(url, data=None, **kwargs):
    try:
        response = requests.post(url, data=data, **kwargs)
    except requests.ConnectionError as e:
        raise ServiceError(599, e.message)

    if response.status_code >= 300:
        raise ServiceError(response.status_code, response.text, response)

    return response


def put(url, data=None, **kwargs):
    try:
        response = requests.put(url, data=data, **kwargs)
    except requests.ConnectionError as e:
        raise ServiceError(599, e.message)

    if response.status_code >= 300:
        raise ServiceError(response.status_code, response.text, response)

    return response


class ServiceError(Exception):
    def __init__(self, code, message, response=None):
        self.code = code
        self.message = message
        self.response = response

    def __str__(self):
        return "Error {0}: {1}".format(str(self.code), self.message)


class ApplicationInfo(object):
    def __init__(self, app_name, app_version, gamespace):
        self.app_name = app_name
        self.app_version = app_version
        self.gamespace = gamespace


class Service(object):
    def __init__(self, location):
        self.location = location
        log("New service: {0} at {1}".format(self.ID, self.location))

    def get(self, url, params):
        params.update({
            "access_token": Login.TOKEN,
        })

        result = get(self.location + "/" + url, params=params)
        return result.json()

    def post(self, url, data):
        data.update({
            "access_token": Login.TOKEN,
        })

        result = post(self.location + "/" + url, data=data)
        return result.json()


class Discovery(Service):
    ID = "discovery"

    def __init__(self, location):
        super(Discovery, self).__init__(location)
        self.cache = {}

        Services.discovery = self

    def get_service(self, service, *args, **kwargs):

        if not isinstance(service, (str, unicode)):
            raise ServiceError(400, "Service should be a string")

        cached = self.cache.get(service, None)
        if cached:
            return cached

        log("Looking for service: " + service)

        response = get(self.location + "/service/" + service)
        location = response.text

        service = Services.new_service(service, location, *args, **kwargs)
        self.cache[service] = service
        return service

    def get_services(self, services, args=None):

        if args is None:
            args = {}

        result = {}

        if not isinstance(services, list):
            raise ServiceError(400, "Service should be a list")

        to_request = []

        for service in services:
            cached = self.cache.get(service, None)
            if cached:
                result[service] = cached
            else:
                to_request.append(service)

        log("Looking for services: " + ",".join(to_request))

        response = get(self.location + "/services/" + ",".join(to_request))
        response_json = response.json()

        for service_id, location in response_json.iteritems():
            _args, _kwargs = args.get(service_id, ([], {}))
            service = Services.new_service(service_id, location, *_args, **_kwargs)
            self.cache[service_id] = service
            result[service_id] = service

        return result


class Environment(Service):
    ID = "environment"

    def __init__(self, location, app_info):
        super(Environment, self).__init__(location)

        self.app_info = app_info
        self.env = {}
        self.discovery = None

        Services.env = self

    def init(self):
        response = get(
            self.location + "/" + self.app_info.app_name + "/" + self.app_info.app_version)

        self.env = response.json()

        try:
            self.discovery = Discovery(self.env["discovery"])
        except KeyError:
            raise ServiceError(500, "No discovery in environment info!")

        log("Got environment response!")
        log("Discovery: " + self.discovery.location)


class Login(Service):
    ID = "login"
    TOKEN = None

    def __init__(self, location):
        super(Login, self).__init__(location)

    def auth(self, credential, scopes, options):
        if not isinstance(scopes, list):
            raise ServiceError(400, "Scopes should be a list")

        app_info = Services.env.app_info

        data = {
            "credential": credential,
            "scopes": ",".join(scopes),
            "gamespace": app_info.gamespace,
            "full": "true"
        }

        data.update(options)

        response = post(self.location + "/auth", data=data)

        token = response.json()["token"]
        Login.TOKEN = token

        log("Authenticated!")

        return token

    def auth_dev(self, username, password, scopes, options=None):

        if options is None:
            options = {}

        options.update({
            "username": username,
            "key": password
        })

        return self.auth("dev", scopes, options)


class Admin(Service):
    ID = "admin"

    def __init__(self, location):
        super(Admin, self).__init__(location)

    @staticmethod
    def find_entry(response, entry_id):
        for entry in response:
            if entry.get("id") == entry_id:
                return entry
        return None

    def api_get(self, service, action, context):
        result = get(self.location + "/api", params={
            "access_token": Login.TOKEN,
            "service": service,
            "context": json.dumps(context),
            "action": action
        })
        return result

    def api_post(self, service, action, method, context, data):

        args = {
            "access_token": Login.TOKEN,
            "service": service,
            "method": method,
            "context": json.dumps(context),
            "action": action
        }

        args.update(data)

        result = post(self.location + "/api", data=args)

        return result

    def api_put(self, service, action, context, data, args=None, **kwargs):

        request_args = {
            "access_token": Login.TOKEN,
            "service": service,
            "context": json.dumps(context),
            "action": action,
            "args": json.dumps(args) if args else "{}"
        }

        try:
            result = put(self.location + "/service/upload?" + urllib.urlencode(request_args), data=data, **kwargs)
        except ServiceError as e:
            if e.code == 444:
                return e.response

            if e.code == 244:
                return e.response

            raise e
        return result


class GenericService(Service):
    def __init__(self, service_id, location):
        self.ID = service_id
        super(GenericService, self).__init__(location)
        log("No service {0} registered, used GenericService".format(service_id))


class Services:
    SERVICES = [
        Environment,
        Discovery,
        Login,
        Admin
    ]

    __wrappers__ = {
        service.ID: service
        for service in SERVICES
    }

    env = None
    discovery = None

    @staticmethod
    def new_service(service_id, location, *args, **kwargs):
        try:
            return Services.__wrappers__[service_id](location, *args, **kwargs)
        except KeyError:
            return GenericService(service_id, location)
