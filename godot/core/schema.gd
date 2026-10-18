class_name Schema
extends RefCounted
## A tiny structural validator for server frames. Anything that reaches a model builder has passed it, so builders
## never index into a value of the wrong shape (review N03).
##
## A spec is one of:
##   TYPE_STRING / TYPE_INT / TYPE_BOOL / TYPE_DICTIONARY / TYPE_ARRAY   exact Variant type
##   Schema.NUM                          int or float
##   Schema.ANY                          anything, including null
##   {"list": spec}                      array whose every element matches spec
##   {"map": spec}                       object whose every value matches spec
##   {"null": spec}                      null, or spec
##   {"dict": {"key": spec, "?key": spec}}   object with these keys; a leading "?" makes the key optional

const NUM := -1
const ANY := -2


## "" when `v` matches `spec`, else a short description of the first problem.
static func check(v: Variant, spec: Variant, path := "$") -> String:
	if spec is int:
		if spec == ANY:
			return ""
		var got := typeof(v)
		if spec == NUM:
			return "" if got == TYPE_INT or got == TYPE_FLOAT else "%s is not a number" % path
		return "" if got == spec else "%s has the wrong type" % path
	var d: Dictionary = spec
	if d.has("null"):
		return "" if v == null else check(v, d["null"], path)       # `null` is a keyword: index, don't use d.null
	if d.has("list"):
		if not (v is Array):
			return "%s is not a list" % path
		for i in v.size():
			var p := check(v[i], d.list, "%s[%d]" % [path, i])
			if p != "":
				return p
		return ""
	if d.has("map"):
		if not (v is Dictionary):
			return "%s is not an object" % path
		for k in v:
			var p := check(v[k], d.map, "%s.%s" % [path, k])
			if p != "":
				return p
		return ""
	if d.has("dict"):
		if not (v is Dictionary):
			return "%s is not an object" % path
		for k in d.dict:
			var optional := str(k).begins_with("?")
			var key := str(k).substr(1) if optional else str(k)
			if not v.has(key):
				if optional:
					continue
				return "%s.%s is missing" % [path, key]
			var p := check(v[key], d.dict[k], "%s.%s" % [path, key])
			if p != "":
				return p
		return ""
	return "%s: bad spec" % path
