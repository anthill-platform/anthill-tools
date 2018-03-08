
from anthill_tools import Discovery, Environment, Login, Admin, ApplicationInfo, ServiceError

import hashlib
import os
import sys
import json
from optparse import OptionParser


def log(data):
    print data


def md5(file_name):
    hash_ = hashlib.md5()

    with open(file_name, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_.update(chunk)

    return hash_.hexdigest()


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


class Bundle(object):
    def __init__(self):
        self.name = None
        self.path = None
        self.hash = None
        self.size = 0
        self.filters = {}
        self.properties = {}

    def init(self):
        bundle_path = self.path
        if not os.path.isfile(bundle_path):
            raise DeliverError("Bundle {0} cannot be found!".format(bundle_path))
        self.hash = md5(bundle_path)
        self.size = os.path.getsize(bundle_path)


class Deliverer(object):
    def __init__(self, environment_location, app_info, config, username=None, password=None, force=False):
        self.environment_location = environment_location
        self.app_info = app_info
        self.username = username
        self.password = password
        self.force = force

        self.bundles = []

        self.upload_bundles = []
        self.attach_bundles = []

        self.env = None
        self.discovery = None
        self.login = None
        self.admin = None
        self.dlc = None

        self.init()
        self.parse_config(config)

    def parse_config(self, config):
        log("Parsing config...")
        if "bundles" in config:
            if not isinstance(config["bundles"], dict):
                raise DeliverError("bundles should be a dict")

            for name, config_bundle in config["bundles"].iteritems():
                if "path" not in config_bundle:
                    raise DeliverError("Bundle has no path option")

                bundle = Bundle()
                bundle.name = name
                bundle.path = config_bundle["path"]
                bundle.filters = config_bundle.get("filters", {})
                bundle.properties = config_bundle.get("properties", {})

                self.bundles.append(bundle)

    def init(self):
        log("Initializing...")

        self.env = Environment(self.environment_location, self.app_info)
        self.env.init()

        self.discovery = self.env.discovery

        services = self.discovery.get_services([Login.ID, Admin.ID, "dlc"])

        self.login = services[Login.ID]
        self.admin = services[Admin.ID]
        self.dlc = services["dlc"]

    def deliver(self):
        log("Authenticating...")

        username = self.username or os.environ.get("ANTHILL_USERNAME")

        if not username:
            raise DeliverError("Please define ANTHILL_USERNAME environment variable.")

        password = self.password or os.environ.get("ANTHILL_PASSWORD")

        if not password:
            raise DeliverError("Please define ANTHILL_PASSWORD environment variable.")

        self.login.auth_dev(username, password, ["admin", "dlc", "dlc_admin"], options={
            "as": "deployer"
        })

        log("Gathering bundles...")

        for bundle in self.bundles:
            bundle.init()

            try:
                self.dlc.get("bundle", params={
                    "bundle_name": bundle.name,
                    "bundle_hash": bundle.hash
                })
            except ServiceError as e:
                if e.code == 404:
                    self.upload_bundles.append(bundle)
                else:
                    raise DeliverError("Failed to check bundle {0}: {1}".format(bundle.name, e.message))
            else:
                self.attach_bundles.append(bundle)

        if self.upload_bundles:
            log("Bundles to upload:")
            total_size = 0
            for bundle in self.upload_bundles:
                log("  {1} [{0}] {2}".format(bundle.hash, bundle.name, sizeof_fmt(bundle.size)))
                total_size += bundle.size
            log("Total size: {0}".format(sizeof_fmt(total_size)))

        if self.attach_bundles:
            log("Existing bundles to attach:")
            for bundle in self.attach_bundles:
                log("  {1} [{0}] {2}".format(bundle.hash, bundle.name, sizeof_fmt(bundle.size)))

        if (not self.upload_bundles) and (not self.attach_bundles):
            log("Nothing to deliver, exiting!")
            return

        if not self.force:
            if not self.upload_bundles:
                proceed = ask("***** There's nothing to upload, "
                              "are you sure you want to create new data entry?")
                if not proceed:
                    log("Exiting!")
                    return
            else:
                proceed = ask("Proceed?")
                if not proceed:
                    log("Exiting!")
                    return

        log("Creating new data version")

        response = self.admin.api_post("dlc", "app", "new_data_version", {
            "app_id": self.app_info.app_name
        }, data={})

        try:
            context = json.loads(response.headers["X-Api-Context"])
        except (KeyError, ValueError):
            raise DeliverError("Failed to get data context")

        data_id = context["data_id"]
        log("New data created: {0}".format(data_id))

        for bundle in self.attach_bundles:
            log("Attaching bundle {0} ...".format(bundle.name))

            self.admin.api_post("dlc", "attach_bundle", "attach", {
                "app_id": self.app_info.app_name,
                "data_id": data_id
            }, data={
                "bundle_name": bundle.name,
                "bundle_hash": bundle.hash
            })

            log("  Attached!")

        for bundle in self.upload_bundles:
            log("Uploading bundle {0} ...".format(bundle.name))

            log("  Creating...")
            response = self.admin.api_post("dlc", "new_bundle", "create", {
                "app_id": self.app_info.app_name,
                "data_id": data_id
            }, data={
                "bundle_name": bundle.name,
                "bundle_payload": json.dumps(bundle.properties),
                "bundle_filters": json.dumps(bundle.filters)
            })

            try:
                context = json.loads(response.headers["X-Api-Context"])
            except (KeyError, ValueError):
                raise DeliverError("Failed to get data context")

            bundle_id = context["bundle_id"]
            log("  New bundle created: {0}".format(bundle_id))

            log("  Uploading...")

            with open(bundle.path, "rb") as f:
                self.admin.api_put("dlc", "bundle", {
                    "app_id": self.app_info.app_name,
                    "data_id": data_id,
                    "bundle_id": bundle_id,
                }, data=f)

            log("  Uploaded!")

        log("Publishing data!")

        self.admin.api_post("dlc", "data_version", "publish", {
            "app_id": self.app_info.app_name,
            "data_id": data_id
        }, data={})

        log("Publish process started!")


def deploy(environment_location, application_name, application_version,
           gamespace, config_location, username=None, password=None, force=False):

    app_info = ApplicationInfo(application_name, application_version, gamespace)

    with open(config_location, "r") as f:
        config = json.load(f)

    d = Deliverer(environment_location, app_info, config, username=username, password=password, force=force)
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

    try:
        deploy(
            environment_location=options.environment_location,
            application_name=options.application_name,
            application_version=options.application_version,
            gamespace=options.gamespace,
            config_location=options.config,
            force=options.force)
    except DeliverError as e:
        print "ERROR: " + e.message
        exit(1)
