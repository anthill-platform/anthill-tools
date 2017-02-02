
from anthill_tools import Discovery, Environment, Login, Admin, ApplicationInfo, ServiceError

import hashlib
import os
import sys
import json
import difflib

from optparse import OptionParser


def log(data):
    print data


def sha256(file_name):
    hash_sha256 = hashlib.sha256()

    with open(file_name, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_sha256.update(chunk)

    return hash_sha256.hexdigest()


def sizeof_fmt(num, suffix='B'):
    for unit in ['', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


class DeliverError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


def ask(question, default="yes"):

    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = raw_input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


class Script(object):
    def __init__(self):
        self.name = None
        self.path = None
        self.imports = []
        self.data = ""

    def init(self):
        if not os.path.isfile(self.path):
            raise DeliverError("Script {0} cannot be found!".format(self.path))

        with open(self.path, 'r') as f:
            self.data = f.read()


class Synchronizer(object):
    def __init__(self, environment_location, app_info, config, username=None, password=None, force=False):
        self.environment_location = environment_location
        self.app_info = app_info
        self.username = username
        self.password = password
        self.force = force

        self.functions = []

        self.create_functions = []
        self.update_functions = []

        self.env = None
        self.discovery = None
        self.login = None
        self.admin = None
        self.dlc = None

        self.init()
        self.parse_config(config)

    def parse_config(self, config):
        log("Parsing config...")
        if "functions" in config:
            if not isinstance(config["functions"], dict):
                raise DeliverError("functions should be a dict")

            for name, config_function in config["functions"].iteritems():
                if "path" not in config_function:
                    raise DeliverError("Script has no path option")

                script = Script()
                script.name = name
                script.path = config_function["path"]
                script.imports = config_function.get("imports", [])

                self.functions.append(script)

    def init(self):
        log("Initializing...")

        self.env = Environment(self.environment_location, self.app_info)
        self.env.init()

        self.discovery = self.env.discovery

        services = self.discovery.get_services([Login.ID, Admin.ID])

        self.login = services[Login.ID]
        self.admin = services[Admin.ID]

    def deliver(self):
        log("Authenticating...")

        username = self.username or os.environ.get("ANTHILL_USERNAME")

        if not username:
            raise DeliverError("Please define ANTHILL_USERNAME environment variable.")

        password = self.password or os.environ.get("ANTHILL_PASSWORD")

        if not password:
            raise DeliverError("Please define ANTHILL_PASSWORD environment variable.")

        self.login.auth_dev(username, password, ["admin", "exec_admin"], options={
            "as": "synchronizer"
        })

        log("Syncing functions...")

        for function in self.functions:
            function.init()

            try:
                result = self.admin.api_get("exec", "function", context={
                    "function_name": function.name
                })
            except ServiceError as e:
                if e.code == 445:
                    self.create_functions.append(function)
                else:
                    raise DeliverError("Failed to check function {0}: {1}".format(function.name, e.message))
            else:
                result = Admin.find_entry(result.json(), "function")
                if result:
                    fields = result.get("fields", {})
                    code = fields.get("code", {}).get("value", "")
                    imports = fields.get("imports", {}).get("value", "")

                    if (unicode(code) != unicode(function.data)) or (",".join(function.imports) != imports):
                        self.update_functions.append(function)

        if self.update_functions:
            log("Functions to update:")
            for function in self.update_functions:
                log("  [{0}]".format(function.name))

        if self.create_functions:
            log("Functions to create:")
            for function in self.create_functions:
                log("  [{0}]".format(function.name))

        if (not self.create_functions) and (not self.update_functions):
            log("Nothing to sync, exiting!")
            return

        for function in self.create_functions:
            log("Creating function {0} ...".format(function.name))

            self.admin.api_post("exec", "new_function", "create", {}, data={
                "name": function.name,
                "imports": ",".join(function.imports),
                "code": function.data
            })

            log("  Created!")

        for function in self.update_functions:
            log("Updating function {0} ...".format(function.name))

            self.admin.api_post("exec", "function", "update", {
                "function_name": function.name
            }, data={
                "name": function.name,
                "imports": ",".join(function.imports),
                "code": function.data
            })

            log("  Updated!")


def sync(environment_location, application_name, application_version,
         gamespace, config_location, username=None, password=None, force=False):

    app_info = ApplicationInfo(application_name, application_version, gamespace)

    with open(config_location, "r") as f:
        config = json.load(f)

    d = Synchronizer(environment_location, app_info, config, username=username, password=password, force=force)
    d.deliver()


if __name__ == "__main__":

    parser = OptionParser()
    parser.add_option("-e", "--environment", dest="environment_location", help="Environment Service Location")
    parser.add_option("-n", "--name", dest="application_name", help="Application Name")
    parser.add_option("-v", "--version", dest="application_version", help="Application Version")
    parser.add_option("-g", "--gamespace", dest="gamespace", help="Gamespace")
    parser.add_option("-c", "--config", dest="config", help="Configuration file")
    parser.add_option("-f", "--force", action="store_true", dest="force", default=False, help="Force yes")

    (options, args) = parser.parse_args()

    if not options.environment_location:
        parser.error('environment not given')
    if not options.application_name:
        parser.error('name not given')
    if not options.application_version:
        parser.error('version not given')
    if not options.gamespace:
        parser.error('gamespace not given')
    if not options.config:
        parser.error('config not given')

    try:
        sync(
            environment_location=options.environment_location,
            application_name=options.application_name,
            application_version=options.application_version,
            gamespace=options.gamespace,
            config_location=options.config,
            force=options.force)
    except DeliverError as e:
        print "ERROR: " + e.message
        exit(1)
