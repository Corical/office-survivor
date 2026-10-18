class_name Clock
extends RefCounted
## The clock port: monotonic milliseconds. Never the phone's wall clock. Tests use a settable subclass.

func now_msec() -> int:
	return Time.get_ticks_msec()
