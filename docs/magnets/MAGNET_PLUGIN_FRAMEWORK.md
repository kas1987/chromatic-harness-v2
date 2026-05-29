# Magnet Plugin Framework

Register custom magnets at runtime without editing `MagnetOrchestrator` or core magnet classes.

## Python

```python
from magnets.plugin import MagnetPlugin, MagnetRegistry, default_registry
from magnets.base_magnet import MagnetEvent

class MyDomainPlugin(MagnetPlugin):
    name = "my_domain_plugin"

    def observe(self, mission_id, inflection_point, signal):
        # return MagnetEvent with risk_delta / evidence
        ...

orch = MagnetOrchestrator()
orch.register_plugin(MyDomainPlugin())
```

**Built-in registry** (`default_registry()`):

- All legacy `BaseMagnet` adapters (intake, intent, scope, execution, cost, confidence, …)
- `pyramid_check_plugin` — test pyramid validation
- `secrets_surface_plugin` — example security surface

## TypeScript (roach-pi / runtime)

```typescript
import { MagnetPluginRegistry, BaseMagnetPluginAdapter } from '../magnets/magnet-plugin';

const registry = MagnetPluginRegistry.global();
registry.register(new BaseMagnetPluginAdapter(new MyMagnet(), 'my_magnet'));
const reports = registry.collectReports();
```

Default runtime registry: `execution`, `cost`, `confidence`.

## Extension points

| Hook | Use |
|------|-----|
| `observe()` | Per inflection signal (required) |
| `on_mission_start()` | Optional Python lifecycle |
| `on_mission_end()` | Optional Python lifecycle |

## Config

`config/magnets/plugins.yaml` — reserved for dynamic class loading (future).
