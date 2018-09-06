[general]
path = string(default='')
hops = integer(defeault=0)
credit_mining = boolean(default=False)
user_stopped = boolean(default=False)
time_added = integer(default=0)
selected_files = string_list(default=list())
metainfo = string(default=None)

[seeding]
safe = boolean(default=True)
mode = string(default='forever')
time = integer(default=60)
ratio = float(default=2.0)

[state]
engineresumedata = string(default=None)
