The gateway expects the UWB firmware/bridge to emit one JSON line per event, for example:

{"tag_id":"T001","rssi_dbm":-74.2,"toa_ns":1700000000123456789}

These values ​​are transformed into:

Measurement.toa_ns → hardware timestamp/event time for ToA/TDoA

Measurement.rssi_dbm → optional

Measurement.channel = "UWB-SERIAL"