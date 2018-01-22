import json

class Storage_backend_json(object):

    def __init__(self, filename):
        self.filename = filename

    def save(self, data):
        with open(self.filename, "w") as file:
            json.dump(data, file)

    def load(self):
        with open(self.filename, "r") as file:
            return json.load(file)
