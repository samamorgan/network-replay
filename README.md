# network-replay

## Records and replays network interactions

### Installing

```
pip install network-replay
```

### Quick Start

```python
from network_replay import replay
import requests


@replay
def test_request():
    requests.get("https://httpbin.org/status/200")
```
