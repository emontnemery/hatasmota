# HATasmota

HATasmota is a Python module designed to interact with [Tasmota](https://tasmota.github.io/docs/) devices via MQTT. It provides a structured way to handle device discovery, status monitoring, and control.

This library is primarily used by the [Home Assistant Tasmota integration](https://www.home-assistant.io/integrations/tasmota/).

## Features

- **Tasmota Device Discovery**: Automatic identification of Tasmota devices on the network.
- **Component Support**: Broad support for various Tasmota components, including Relays, Sensors, Shutters, Fans, and Triggers.
- **Firmware Updates**: Manage Tasmota firmware updates via MQTT using the `Status 2` and `Upgrade` commands.

## Firmware Updates

HATasmota supports updating official Tasmota firmware. To ensure stability, the integration filters builds to ensure only safe, official binaries are used for auto-updates.

### Supported Versions

Official stable releases are supported. The integration identifies "Stock" builds based on their variant name in the version string.

| Build Type | Variants / Patterns | Status |
| :--- | :--- | :---: |
| **Standard** | `tasmota` (incl. `4M`), `tasmota32` family (S2, S3, C2, C3, C5, C6, P4, solo1) | ✅ Supported |
| **Localized** | `tasmota-AD` to `tasmota-VN`, `tasmota32-AD` to `tasmota32-VN` | ✅ Supported |
| **Feature Set** | `sensors`, `display`, `ir`, `knx`, `zbbridge`, `zigbee`, `lite`, `bluetooth`, `lvgl`, `nspanel`, `webcam`, `zbbridgepro` | ✅ Supported |
| **Minimal** | `minimal`, `tasmota-minimal` | ❌ Excluded |
| **Legacy** | Versions older than `9.1.0` | ❌ Excluded |
| **Custom** | Any custom name, e.g., `(my-custom-build)` | ❌ Excluded |

### Excluded Builds (Safety First)

The "Excluded" builds in the table above are withheld from the update check to prevent device instability:

- **Minimal Builds**: `minimal`, `tasmota-minimal`. These are transitional builds used only during the update process and should never be the final running firmware.
- **Custom Builds**: Any version with a custom variant name (e.g., `(my-custom-build)`).

## More Information

For more details on how to use Tasmota with Home Assistant, please refer to the official documentation:

[Home Assistant Tasmota Integration](https://www.home-assistant.io/integrations/tasmota/)
