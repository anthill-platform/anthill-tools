import os
from optparse import OptionParser

from anthill_tools import Environment, Login, Admin, ApplicationInfo


def log(data):
    print(data)


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

        self.create_version_name = None
        self.create_version_env = None

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

    def create_version(self, version_name, create_version_env):
        self.create_version_name = version_name
        self.create_version_env = create_version_env

    def deliver(self):
        log("Authenticating...")

        rights = ["admin", "game_deploy_admin"]
        if self.create_version_name:
            rights.append("env_admin")

        self.login.auth_dev(self.username, self.password, rights, options={
            "as": "deployer"
        })

        if self.create_version_name:
            log("Creating new version {0} for dev {1}...".format(self.create_version_name, self.create_version_env))

            try:
                self.admin.api_post("environment", "new_app_version", "create", {
                    "app_id": self.app_info.app_name
                }, {
                    "version_name": self.create_version_name,
                    "version_env": self.create_version_env
                })
            except Exception as e:
                log("Version was not created (already exist?)")

        log("Deploying...")

        with open(self.filename, "rb") as f:
            self.admin.api_put("game", "deploy", {
                "game_name": self.app_info.app_name,
                "game_version": self.app_info.app_version
                if self.create_version_name is None else self.create_version_name
            }, f, args={
                "switch_to_new": self.switch
            }, headers={
                "X-File-Name": os.path.basename(self.filename)
            })

        log("Deployed!")


def deploy(environment_location, application_name, application_version,
           gamespace, filename, switch, username=None, password=None,
           create_version=None, create_version_env=None):
    app_info = ApplicationInfo(application_name, application_version, gamespace)

    d = Deliverer(environment_location, app_info, filename, switch, username=username, password=password)

    if create_version and create_version_env:
        d.create_version(create_version, create_version_env)

    d.deliver()


if __name__ == "__main__":

    parser = OptionParser()
    parser.add_option("-e", "--environment", type="string", dest="environment_location",
                      help="Environment Service Location")
    parser.add_option("-n", "--name", type="string", dest="application_name",
                      help="Application Name")
    parser.add_option("-v", "--version", type="string", dest="application_version",
                      help="Application Version")
    parser.add_option("--create-version", type="string", default="", dest="create_version",
                      help="Create a new version")
    parser.add_option("--create-version-env", type="string", default="", dest="create_version_env",
                      help="Environment for new version")
    parser.add_option("-g", "--gamespace", type="string", dest="gamespace",
                      help="Gamespace")
    parser.add_option("-f", "--filename", type="string", dest="filename",
                      help="A filename to deploy")
    parser.add_option("-u", "--username", type="string", dest="anthill_username",
                      help="Anthill Username", default=os.environ.get("ANTHILL_USERNAME"))
    parser.add_option("-p", "--password", type="string", dest="anthill_password",
                      help="Anthill Password", default=os.environ.get("ANTHILL_PASSWORD"))
    parser.add_option("-s", "--switch", type="string", dest="switch_to_new",
                      help="Switch application to deployed version automatically", default="true")

    (options, args) = parser.parse_args()

    defaults = vars(parser.get_default_values())

    for k, v in vars(options).items():
        if v is None and defaults.get(k) is None:
            parser.print_help()
            exit(1)

    try:
        deploy(
            environment_location=options.environment_location,
            application_name=options.application_name,
            application_version=options.application_version,
            create_version=options.create_version,
            create_version_env=options.create_version_env,
            gamespace=options.gamespace,
            filename=options.filename,
            switch=options.switch_to_new,
            username=options.anthill_username,
            password=options.anthill_password)
    except DeliverError as e:
        print("ERROR: " + str(e))
        exit(1)
