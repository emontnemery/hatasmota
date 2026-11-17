# hatasmota

## Firmware update

`hatasmota.update` reads the firmware details of a device (`Status 2`) and can
drive an OTA upgrade of official Tasmota release builds:

- `get_install_blocker()` returns why a firmware must not be upgraded
  automatically (self-built, development, minimal or safeboot build, version
  too old, unknown variant), or `None` for an official release build.
- `TasmotaUpdate.reset_ota_url()` sends `OtaUrl 1`. The device falls back to the
  OtaUrl its firmware was compiled with, which for official builds points to the
  image of its own variant on ota.tasmota.com. Check it with
  `is_official_ota_url()` before calling `TasmotaUpdate.start_upgrade()`
  (`Upgrade 1`).
