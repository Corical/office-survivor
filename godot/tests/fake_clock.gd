class_name FakeClock
extends Clock
## A clock the test moves by hand.

var t := 1000


func now_msec() -> int:
	return t


func advance(ms: int) -> void:
	t += ms
