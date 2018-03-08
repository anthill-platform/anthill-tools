# Anthill Tools

Tool set to communicate with anthill platform

### Installation

```bash
pip install git+https://github.com/anthill-platform/anthill-tools.git
```

# Authentication

Each of the tools below require authentication. Easiest way would be define `ANTHILL_USERNAME` and
`ANTHILL_PASSWORD` environment variables before making the call. But you can also pass
these via `--username` and `--password` command line arguments, but you are exposing these in that case.

# DLC content deployment

This configurations allows to deliver various bundles onto DLC service.

Command line usage:

```bash
python -m anthill_tools.admin.dlc.deployer \
  --environment="<environment location>" \
  --name="<game name>" \
  --version="<game version>" \
  --gamespace="<gamespace name>" \
  --config "<JSON configuration file>.json"
```

Python usage:

```python

from anthill_tools.admin.dlc import deployer

deployer.deploy(
    "http://environment-dev.anthill",
    "test",
    "1.0",
    "root",
    "<JSON configuration file>.json",
    username="<username>",
    password="<password>")

```

The bundles to deliver are read from the JSON configuration file. Example of that file:

```json
{
    "bundles": {
        "test.zip": {
            "path": "/Users/.../bundles/test.zip",
            "filters": {
                "os.windows": true,
                "os.osx": true,
                "os.linux": true,
                "os.ios": true,
                "os.android": true
            },
            "settings": {}
        },
        "test2.zip": {
            "path": "/Users/.../bundles/test2.zip",
            "filters": {
                "os.windows": true,
                "os.osx": true,
                "os.linux": true,
                "os.ios": true,
                "os.android": true
            },
            "settings": {}
        }
    }
}
```

# Game Servers deployment

This configurations allows to deliver Game Server builds onto Game Master service.
Each build should be packed into a zip file before deployment.

Command line usage:

```bash
python -m anthill_tools.admin.game.deployer \
  --environment="<environment location>" \
  --name="<game name>" \
  --version="<game version>" \
  --gamespace="<gamespace name>" \
  --filename "<game server files packed into one zip file"
```

Python usage:

```python
from anthill_tools.admin.game import deployer

deployer.deploy(
    "http://environment-dev.anthill",
    "test",
    "1.0",
    "root",
    "game_server.zip",
    switch="true",
    username="<username>",
    password="<password>")
```
