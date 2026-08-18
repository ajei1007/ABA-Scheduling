class Constraint:
    def __init__(self, info):
        self.max = info['max']
        self.min = info['min']
        self.frequency = info['frequency']
        self.constraint = info['constraint']
        self.days = info['days']
        pass


class Resource:
    def __init__(self, info, index):
        self.name = info['name']
        self.id = info['id']
        self.roles = info['roles']
        self.waitlisted = info['waitlisted']
        self.notWorking = info["notWorking"]
        self.matches = {}
        self.matches2 = {}
        self.onlyUserToUser = {}
        self.onlyUserToSession = {}
        self.work_together_arr = {}
        self.sessions_together_arr = {}
        self.time_with_users = {}
        self.events = []
        self.total_time = 0
        self.time_constraints = {'session': {}, 'day': {}, 'week': {}}
        self.time_so_far = 0
        self.rec_time = 0
        self.max_time_obj = {}
        self.slots = {}
        self.activities = {}
        self.index = index


class Resources:
    def __init__(self, resources):
        self.resources = {}
        self.roles = {}
        self.events = []
        self.appointments = []
        self.frequency_constraints = []
        self.drive_constraints = []
        self.onlyUserToUser = {}
        self.onlyUserToSession = {}
        self.slots = {}
        for index, resource in enumerate(resources):
            new_resource = Resource(resource, index)
            self.resources[index] = new_resource

