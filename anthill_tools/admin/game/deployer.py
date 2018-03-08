
import os
from optparse import OptionParser

from anthill_tools import Environment, Login, Admin, ApplicationInfo


def log(data):
    print data

class DeliverError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class Deliverer(object):
    def __init__(self, environment_location, app_info, filename, switch, username=None, password=None):
        self.environment_location = environment_location
        self.app_info = app_info
        self.username = username
        self.password = password
        self.filename = filename
        self.switch = switch

        self.bundles = []

        self.upload_bundles = []
        self.attach_bundles = []

        self.env = None
        self.discovery = None
        self.login = None
        self.admin = None
        self.game = None

        self.init()

    def init(self):
        log("Initializing...")

        self.env = Environment(self.environment_location, self.app_info)
        self.env.init()

        self.discovery = self.env.discovery

        services = self.discovery.get_services([Login.ID, Admin.ID, "game"])

        self.login = services[Login.ID]
        self.admin = services[Admin.ID]
        self.game = services["game"]

    def deliver(self):
        log("Authenticating...")

        username = self.username or os.environ.get("ANTHILL_USERNAME")

        if not username:
            raise DeliverError("Please define ANTHILL_USERNAME environment variable.")

        password = self.password or os.environ.get("ANTHILL_PASSWORD")

        if not password:
            raise DeliverError("Please define ANTHILL_PASSWORD environment variable.")

        self.login.auth_dev(username, password, ["admin", "game_deploy_admin"], options={
            "as": "deployer"
        })

        log("Deploying...")

        with open(self.filename, "rb") as f:
            self.admin.api_put("game", "deploy", {
                "game_name": self.app_info.app_name,
                "game_version": self.app_info.app_version
            }, f, args={
                "switch_to_new": self.switch
            }, headers={
                "X-File-Name": os.path.basename(self.filename)
            })

        log("Deployed!")


def deploy(environment_location, application_name, application_version,
           gamespace, filename, switch, username=None, password=None):

    app_info = ApplicationInfo(application_name, application_version, gamespace)

    d = Deliverer(environment_location, app_info, filename, switch, username=username, password=password)
    d.deliver()


if __name__ == "__main__":

    parser = OptionParser()
    parser.add_option("-e", "--environment", type="string", dest="environment_location",
                      help="Environment Service Location")
    parser.add_option("-n", "--name", type="string", dest="application_name", help="Application Name")
    parser.add_option("-v", "--version", type="string", dest="application_version", help="Application Version")
    parser.add_option("-g", "--gamespace", type="string", dest="gamespace", help="Gamespace")
    parser.add_option("-f", "--filename", type="string", dest="filename", help="A filename to deploy")
    parser.add_option("-s", "--switch", type="string", dest="switch_to_new", default="true",
                      help="Switch application to deployed version automatically")

    (options, args) = parser.parse_args()

    try:
        deploy(
            environment_location=options.environment_location,
            application_name=options.application_name,
            application_version=options.application_version,
            gamespace=options.gamespace,
            filename=options.filename,
            switch=options.switch_to_new)
    except DeliverError as e:
        print "ERROR: " + e.message
        exit(1)
