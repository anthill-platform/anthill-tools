# Anthill Tools

Tool set to communicate with anthill platform

### Installation

```bash
pip install git+https://github.com/anthill-services/anthill-tools.git
```

# DLC content deployment

This configurations allows to deliver various bundles onto DLC service:

`deploy.py`:
```python

from anthill_tools.admin.dlc import deployer

deployer.deploy(
    "http://environment-dev.anthill",
    "test",
    "1.0",
    "root",
    "test.json",
    username="<username>",
    password="<password>")

```

`test.json`:

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

# Exec functions synchronization

This configurations allows to deliver various scripts (functions) onto exec service:

`sync.py`:
```python

from anthill_tools.admin._exec import sync

sync.sync(
    "http://environment-dev.anthill",
    "test",
    "1.0",
    "root",
    "scripts.json",
    username="<username>",
    password="<password>")

```

`scripts.json`:

```json
{
  "functions": {
    "utils": {
      "path": "utils.js",
      "imports": []
    },
    "game": {
      "path": "game.js",
      "imports": ["utils"]
    }
  }
}
```